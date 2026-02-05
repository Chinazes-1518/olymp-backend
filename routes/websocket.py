from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, and_, cast, String, func, update
from sqlalchemy.dialects.postgresql import ARRAY
import asyncio
import json
import time
from typing import Dict, Set, List, Optional

from routes import analytics
from utils import token_to_user
import utils
from .battle import battle_manager, Room
import database
from database import Tasks

router = APIRouter()


def verify_params(data: dict, params: list[str]) -> bool:
    return all(x in data for x in params)


async def start_game_timer(room: Room):
    if room.status != 'waiting':
        return

    room.status = 'started'
    room.start_time = time.time()

    await room.broadcast({
        'event': 'game_started',
        'start_time': room.start_time
    })

    await asyncio.sleep(room.time_limit)

    await room.broadcast({
        'event': 'game_finished',
    })
    room.status = 'finishing'


connected_websockets: list[WebSocket] = []


async def broadcast(data: dict) -> None:
    for s in connected_websockets:
        await s.send_json(data)


async def ws_error(websocket: WebSocket, msg: str):
    await websocket.send_json({
        'event': 'error',
        'message': msg
    })


async def advance_to_next_task(room: Room, session) -> None:
    async with room.task_advance_lock:
        room.current_task_index += 1

        if room.current_task_index >= len(room.task_data):
            await room.broadcast({
                'event': 'all_tasks_completed',
                'message': 'Все задачи пройдены!'
            })
            if hasattr(room, 'timer_task') and room.timer_task:
                room.timer_task.cancel()
                room.status = 'finishing'
                await room.broadcast({'event': 'game_finished'})
            return
        next_task_data = room.task_data[room.current_task_index]

        task = (await session.execute(
            select(database.Tasks).where(database.Tasks.id == next_task_data['id'])
        )).scalar_one_or_none()

        if not task:
            await room.broadcast({
                'event': 'error',
                'message': 'Задача не найдена'
            })
            return

        room.player_answers_received = {
            room.host: False,
            room.other: False
        }

        await room.broadcast({
            'event': 'next_task_available',
            'task': {
                'id': task.id,
                'level': task.level,
                'subcategory': task.subcategory,
                'condition': task.condition,
                'source': task.source,
                'answer_type': task.answer_type,
                'task_index': room.current_task_index,
                'total_tasks': len(room.task_data)
            },
            'task_number': room.current_task_index + 1,
            'total_tasks': len(room.task_data),
            'waiting_for_answers': False
        })

        print(f"Комната {room.id}: Переход к задаче {room.current_task_index + 1}")


async def handle_player_answer(room: Room, user_id: int, task_id: int, answer: str,
                               session, websocket: WebSocket) -> None:
    try:
        task = (await session.execute(
            select(database.Tasks).where(database.Tasks.id == task_id)
        )).scalar_one_or_none()

        if task is None:
            await ws_error(websocket, 'Task not found')
            return

        correct = str(answer).strip() == str(task.answer).strip()

        if user_id == room.host:
            if task.id in room.player_1_stats.solved:
                await ws_error(websocket, 'Task already solved')
                return

            if correct:
                room.player_1_stats.solved.append(task.id)
                room.player_1_stats.points += utils.level_to_points(task.level)
                await websocket.send_json({
                    'event': 'check_result',
                    'correct': True,
                    'points': utils.level_to_points(task.level)
                })

                if room.other_ws:
                    await room.other_ws.send_json({
                        'event': 'other_solved',
                        'points': room.player_2_stats.points
                    })
            else:
                await websocket.send_json({
                    'event': 'check_result',
                    'correct': False
                })

            room.player_1_stats.answers[task.id] = answer

        else:  # player 2
            if task.id in room.player_2_stats.solved:
                await ws_error(websocket, 'Task already solved')
                return

            if correct:
                room.player_2_stats.solved.append(task.id)
                room.player_2_stats.points += utils.level_to_points(task.level)
                await websocket.send_json({
                    'event': 'check_result',
                    'correct': True,
                    'points': utils.level_to_points(task.level)
                })

                if room.host_ws:
                    await room.host_ws.send_json({
                        'event': 'other_solved',
                        'points': room.player_1_stats.points
                    })
            else:
                await websocket.send_json({
                    'event': 'check_result',
                    'correct': False
                })

            room.player_2_stats.answers[task.id] = answer
        room.player_answers_received[user_id] = True

        both_answered = all(room.player_answers_received.values())

        if both_answered:
            await room.broadcast({
                'event': 'both_answered',
                'message': 'Оба игрока ответили. Переход к следующей задаче через 2 секунды...',
                'task_id': task_id
            })

            await asyncio.sleep(2)

            await advance_to_next_task(room, session)
        else:
            other_player_id = room.other if user_id == room.host else room.host
            other_player_answered = room.player_answers_received[other_player_id]

            if not other_player_answered:
                await websocket.send_json({
                    'event': 'waiting_for_other_player',
                    'message': 'Ожидаем ответа второго игрока...'
                })

                other_ws = room.other_ws if user_id == room.host else room.host_ws
                if other_ws:
                    await other_ws.send_json({
                        'event': 'other_player_answered',
                        'message': 'Первый игрок уже ответил. Вы можете дать ответ.'
                    })

    except Exception as e:
        print(f"Ошибка при обработке ответа: {e}")
        await ws_error(websocket, f'Internal server error: {str(e)}')


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = None
    current_room = None
    connected_websockets.append(websocket)

    while True:
        try:
            data = await websocket.receive_json()

            if 'event' not in data or 'token' not in data:
                await ws_error(websocket, 'specify event and token')
                continue

            async with database.sessions.begin() as session:
                user = await token_to_user(session, data['token'])
                if user is None:
                    await ws_error(websocket, 'Failed to verify token')
                    continue

                user_id = user.id
                cmd = data['event']

                if current_room is None:
                    current_room = battle_manager.get_room_by_user(user_id)
                    if current_room is not None:
                        if current_room.host == user_id:
                            current_room.host_ws = websocket
                        elif current_room.other == user_id:
                            current_room.other_ws = websocket

                        if not hasattr(current_room, 'player_answers_received'):
                            current_room.player_answers_received = {
                                current_room.host: False,
                                current_room.other: False
                            }
                        if not hasattr(current_room, 'task_advance_lock'):
                            current_room.task_advance_lock = asyncio.Lock()
                        if not hasattr(current_room, 'current_task_index'):
                            current_room.current_task_index = 0

                if cmd == 'create_room':
                    if not verify_params(data, ['name']):
                        await ws_error(websocket, 'Specify room name')
                        continue

                    existing_room = battle_manager.get_room_by_user(user_id)
                    if existing_room:
                        await ws_error(websocket, 'You are already in a room')
                        continue

                    if not verify_params(data, ['count', 'time_limit']):
                        await ws_error(websocket, 'not enough params')
                        continue

                    room_id = battle_manager.add_room(
                        user_id, websocket, data['name'])
                    current_room = battle_manager.get_room(room_id)

                    level_start = int(data.get('level_start', 0))
                    level_end = int(data.get('level_end', 10))
                    subcategory = data.get('subcategory', None)
                    category = int(data['category']) if 'category' in data else None
                    count = int(data['count'])

                    current_room.category = category
                    current_room.time_limit = int(data['time_limit'])
                    current_room.level_start = level_start
                    current_room.level_end = level_end

<<<<<<< HEAD
                    tasks_data = await utils.filter_tasks(session, level_start, level_end, subcategory, None, category,
                                                          True, count)

                    current_room.task_data = tasks_data
                    current_room.current_task_index = 0
                    current_room.player_answers_received = {
                        current_room.host: False,
                        current_room.other: False
                    }
                    current_room.task_advance_lock = asyncio.Lock()
=======
                    tasks_data = await utils.filter_tasks(session, level_start, level_end, subcategory, None, category, True, count)

                    current_room.task_data = tasks_data
                    print(current_room.task_data)
                    current_room.total_points = sum([utils.level_to_points(x['level']) for x in current_room.task_data])
>>>>>>> 3a40817b830dbbd83c3c7fe90b7da7e9e721e5bc

                    await websocket.send_json({
                        'event': 'your_room_created',
                        'room_id': room_id,
                    })

                    await broadcast({
                        'event': 'room_created',
                        'host': user_id,
                        'id': room_id,
                        'name': data['name'],
                        'host_name': f'{user.name} {user.surname[0]}.'
                    })

                elif cmd == 'join_room':
                    if not verify_params(data, ['room_id']):
                        await ws_error(websocket, 'Specify room id')
                        continue

                    room = battle_manager.get_room(int(data['room_id']))
                    if room is None:
                        await ws_error(websocket, 'Room not found')
                        continue

                    if room.other is not None:
                        await ws_error(websocket, 'Room is already full')
                        continue

                    if user_id == room.host:
                        await ws_error(websocket, 'You are the host')
                        continue

                    battle_manager.user_join_room(user_id, room, websocket)
                    current_room = room

                    if not hasattr(current_room, 'player_answers_received'):
                        current_room.player_answers_received = {
                            current_room.host: False,
                            current_room.other: False
                        }
                    if not hasattr(current_room, 'task_advance_lock'):
                        current_room.task_advance_lock = asyncio.Lock()
                    if not hasattr(current_room, 'current_task_index'):
                        current_room.current_task_index = 0

                    await room.host_ws.send_json({
                        'event': 'player_joined',
                        'user_id': user_id,
                        'name': f'{user.name} {user.surname[0]}.'
                    })

                    await websocket.send_json({
                        'event': 'join_successful'
                    })

                elif cmd == 'start_game':
                    if current_room is None:
                        await ws_error(websocket, 'You are not in a room')
                        continue

                    if user_id != current_room.host:
                        await ws_error(websocket, 'Only host can start game')
                        continue

                    if current_room.other is None:
                        await ws_error(websocket, 'Room is not full yet')
                        continue

                    if current_room.status != 'waiting':
                        await ws_error(websocket, 'Room has already been started')
                        continue

<<<<<<< HEAD
                    await session.execute(
                        update(database.Users).where(database.Users.id == current_room.host).values(status='battle'))
                    await session.execute(
                        update(database.Users).where(database.Users.id == current_room.other).values(status='battle'))

                    if current_room.task_data:
                        first_task = current_room.task_data[0]
                        await current_room.broadcast({
                            'event': 'tasks_selected',
                            'tasks': [
                                {
                                    'id': x['id'],
                                    'level': x['level'],
                                    'subcategory': x['subcategory'],
                                    'condition': x['condition'],
                                    'source': x['source'],
                                    'answer_type': x['answer_type'],
                                }
                                for x in current_room.task_data
                            ],
                            'current_task': first_task,
                            'task_number': 1,
                            'total_tasks': len(current_room.task_data)
                        })
                    else:
                        await ws_error(websocket, 'No tasks available')
                        continue
=======
                    await session.execute(update(database.Users).where(database.Users.id == current_room.host).values(status='battle'))
                    await session.execute(update(database.Users).where(database.Users.id == current_room.other).values(status='battle'))

                    await current_room.broadcast({
                        'event': 'new_task',
                        'index': current_room.current_task,
                        'task': {
                            'id': current_room.task_data[current_room.current_task]['id'],
                            'level': current_room.task_data[current_room.current_task]['level'],
                            'subcategory': current_room.task_data[current_room.current_task]['subcategory'],
                            'condition': current_room.task_data[current_room.current_task]['condition'],
                            'source': current_room.task_data[current_room.current_task]['source'],
                            'answer_type': current_room.task_data[current_room.current_task]['answer_type'],
                        }
                    })
>>>>>>> 3a40817b830dbbd83c3c7fe90b7da7e9e721e5bc

                    current_room.timer_task = asyncio.create_task(start_game_timer(current_room))

                elif cmd == 'send_answer':
                    if not verify_params(data, ['answer', 'time']):
                        await ws_error(websocket, 'Wrong params')
                        continue

                    if current_room is None or current_room.status != 'started':
                        await ws_error(websocket, 'Not in game')
                        continue
                    current_task_id = None
                    if current_room.current_task_index < len(current_room.task_data):
                        current_task_id = current_room.task_data[current_room.current_task_index]['id']

<<<<<<< HEAD
                    if int(data['task_id']) != current_task_id:
                        await ws_error(websocket, 'Это не текущая задача')
                        continue

                    await handle_player_answer(
                        current_room,
                        user_id,
                        int(data['task_id']),
                        data['answer'],
                        session,
                        websocket
                    )

                elif cmd == 'request_next_task_early':
                    if current_room is None or current_room.status != 'started':
                        await ws_error(websocket, 'Not in game')
                        continue

                    if not current_room.player_answers_received.get(user_id, False):
                        await ws_error(websocket, 'Сначала ответьте на текущую задачу')
                        continue

                    other_player_ws = current_room.other_ws if user_id == current_room.host else current_room.host_ws
                    if other_player_ws:
                        await other_player_ws.send_json({
                            'event': 'next_task_requested',
                            'message': 'Второй игрок хочет перейти к следующей задаче. Вы согласны?'
                        })

                        await websocket.send_json({
                            'event': 'next_task_request_sent',
                            'message': 'Запрос отправлен второму игроку'
                        })

                elif cmd == 'accept_next_task':
                    """Подтверждение перехода к следующей задаче"""
                    if current_room is None or current_room.status != 'started':
                        await ws_error(websocket, 'Not in game')
                        continue


                    await advance_to_next_task(current_room, session)


=======
                    task = (await session.execute(select(database.Tasks).where(database.Tasks.id == int(current_room.task_data[current_room.current_task]['id'])))).scalar_one_or_none()
                    if task is None:
                        await ws_error(websocket, 'Task not found')
                        continue

                    correct = utils.gigachat_check_answer(data['answer'].strip(), task.condition, task.answer).lower() == 'да'

                    if correct:
                        if user_id == current_room.host:  # player 1
                            if current_room.player_1_stats.answered:
                                await ws_error(websocket, 'Task already solved')
                                continue
                            await current_room.other_ws.send({'event': 'other_solved', 'total_points': current_room.player_2_stats.points})
                            current_room.player_1_stats.answered = True
                            current_room.player_1_stats.times.append(int(data['time']))
                            current_room.player_1_stats.points += utils.level_to_points(
                                task.level)
                        else:  # player 2
                            if current_room.player_2_stats.answered:
                                await ws_error(websocket, 'Task already solved')
                                continue
                            await current_room.host_ws.send({'event': 'other_solved', 'total_points': current_room.player_1_stats.points})
                            current_room.player_2_stats.answered = True
                            current_room.player_2_stats.times.append(int(data['time']))
                            current_room.player_2_stats.points += utils.level_to_points(
                                task.level)
                        await websocket.send({'event': 'check_result', 'correct': True, 'points': utils.level_to_points(task.level)})
                    else:
                        await websocket.send({'event': 'check_result', 'correct': False})

                    current_room.player_1_stats.answers |= {task.id: data['answer']}

                    if current_room.player_1_stats.answered and current_room.player_2_stats.answered:
                        current_room.player_1_stats.answered = False
                        current_room.player_2_stats.answered = False

                        current_room.current_task += 1
                        if current_room.current_task == len(current_room.task_data):
                            score_1_now = (await session.execute(select(database.Users).where(database.Users.id == current_room.host))).scalar_one().points
                            score_2_now = (await session.execute(select(database.Users).where(database.Users.id == current_room.other))).scalar_one().points
                            total_points = sum([utils.level_to_points(
                                x['level']) for x in current_room.task_data])

                            score1new, score2new = utils.calculate_elo_rating(
                                score_1_now, score_2_now, current_room.player_1_stats.points / total_points, current_room.player_2_stats.points / total_points)

                            t1 = current_room.player_1_stats.times
                            t2 = current_room.player_2_stats.times

                            await current_room.broadcast({
                                'event': 'scores',
                                'player1_new': score1new,
                                'player1_correct': len(current_room.player_1_stats.solved),
                                'player1_avgtime': sum(t1) / len(t1) if len(t1) > 0 else 0,
                                'player2_new': score2new,
                                'player2_correct': len(current_room.player_2_stats.solved),
                                'player2_avgtime': sum(t2) / len(t2) if len(t2) > 0 else 0,
                            })

                            await session.execute(update(database.Users).where(database.Users.id == current_room.host).values(status=None, score=score1new))
                            await session.execute(update(database.Users).where(database.Users.id == current_room.other).values(status=None, score=score2new))

                            await analytics.change_values(current_room.host, {'task_quantity': len(current_room.task_data), 'answer_quantity': len(current_room.task_data), 'time_per_task': {
                                current_room.task_data[i]['id']:current_room.player_1_stats.times[i] for i in range(len(current_room.task_data))
                            }})
                            await analytics.change_values(current_room.other, {'task_quantity': len(current_room.task_data), 'answer_quantity': len(current_room.task_data), 'time_per_task': {
                                current_room.task_data[i]['id']:current_room.player_2_stats.times[i] for i in range(len(current_room.task_data))
                            }})

                            battle_manager.remove_room(current_room)
                            current_room = None
                        else:
                            await current_room.broadcast({
                                'event': 'new_task',
                                'index': current_room.current_task,
                                'task': {
                                    'id': current_room.task_data[current_room.current_task]['id'],
                                    'level': current_room.task_data[current_room.current_task]['level'],
                                    'subcategory': current_room.task_data[current_room.current_task]['subcategory'],
                                    'condition': current_room.task_data[current_room.current_task]['condition'],
                                    'source': current_room.task_data[current_room.current_task]['source'],
                                    'answer_type': current_room.task_data[current_room.current_task]['answer_type'],
                                }
                            })
>>>>>>> 3a40817b830dbbd83c3c7fe90b7da7e9e721e5bc
                elif cmd == 'send_to_chat':
                    if not verify_params(data, ['message']):
                        await ws_error(websocket, 'No message specified')
                        continue

                    room = battle_manager.get_room_by_user(user_id)
                    if room is None:
                        await ws_error(websocket, 'Not in room')
                        continue

                    await room.broadcast({
                        'event': 'chat_message',
                        'sender': f'{user.name} {user.surname}',
                        'message': data['message'],
                        'time': time.strftime("%H:%M:%S")
                    })

                elif cmd == 'get_game_state':
                    if current_room is None:
                        await ws_error(websocket, 'Not in a room')
                        continue

                    current_task = None
                    if (current_room.current_task_index < len(current_room.task_data) and
                            current_room.task_data):
                        task_data = current_room.task_data[current_room.current_task_index]
                        current_task = {
                            'id': task_data['id'],
                            'level': task_data['level'],
                            'subcategory': task_data['subcategory'],
                            'condition': task_data['condition'],
                            'source': task_data['source'],
                            'answer_type': task_data['answer_type'],
                        }

                    res = current_room.json()
                    if user_id == current_room.host:
                        other_user = await utils.user_by_id(session, current_room.other)
                        res |= {
                            'answers': current_room.player_1_stats.answers,
                            'points': current_room.player_1_stats.points,
                            'solved': current_room.player_1_stats.solved,
<<<<<<< HEAD
                            'other_points': current_room.player_2_stats.points,
                            'other_name': f'{user.name} {user.surname[0]}.',
                            'current_task_index': current_room.current_task_index,
                            'current_task': current_task,
                            'player_answered': current_room.player_answers_received.get(user_id, False),
                            'other_answered': current_room.player_answers_received.get(current_room.other, False)
=======
                            'other_points': current_room.player_2_stats.points
>>>>>>> 3a40817b830dbbd83c3c7fe90b7da7e9e721e5bc
                        }
                    else:
                        other_user = await utils.user_by_id(session, current_room.host)
                        res |= {
                            'answers': current_room.player_2_stats.answers,
                            'points': current_room.player_2_stats.points,
                            'solved': current_room.player_2_stats.solved,
                            'other_points': current_room.player_1_stats.points,
                            'other_name': f'{other_user.name} {other_user.surname[0]}.',
                            'current_task_index': current_room.current_task_index,
                            'current_task': current_task,
                            'player_answered': current_room.player_answers_received.get(user_id, False),
                            'other_answered': current_room.player_answers_received.get(current_room.host, False)
                        }

                    res['task'] = {
                        'id': current_room.task_data[current_room.current_task]['id'],
                        'level': current_room.task_data[current_room.current_task]['level'],
                        'subcategory': current_room.task_data[current_room.current_task]['subcategory'],
                        'condition': current_room.task_data[current_room.current_task]['condition'],
                        'source': current_room.task_data[current_room.current_task]['source'],
                        'answer_type': current_room.task_data[current_room.current_task]['answer_type'],
                    }
                    res['event'] = 'game_state'
                    await websocket.send_json(res)
<<<<<<< HEAD

                elif cmd == 'finish':
                    if not verify_params(data, ['times']):
                        await ws_error(websocket, 'Times not specified')
                        continue
                    if current_room is None:
                        await ws_error(websocket, 'Not in a room')
                        continue
                    if current_room.status != 'started':
                        await ws_error(websocket, 'Game is not running')
                        continue
                    if user.id == current_room.host:
                        current_room.player_1_stats.finished = True
                        current_room.player_1_stats.times = data['times']
                        await current_room.other_ws.send_json({
                            'event': 'other_finished'
                        })
                    else:
                        current_room.player_2_stats.finished = True
                        current_room.player_2_stats.times = data['times']
                        await current_room.other_ws.send_json({
                            'event': 'other_finished'
                        })
                    if current_room.player_1_stats.finished and current_room.player_2_stats.finished:
                        current_room.timer_task.cancel()
                        current_room.status = 'finishing'
                        await current_room.broadcast({'event': 'game_finished'})

                elif cmd == 'player_times':
                    if not verify_params(data, ['times']):
                        await ws_error(websocket, 'Times not specified')
                        continue
                    if current_room is None or current_room.status != 'finishing':
                        await ws_error(websocket, 'error')
                        continue
                    if user.id == current_room.host:
                        current_room.player_1_stats.times = data['times']
                    else:
                        current_room.player_2_stats.times = data['times']
                    if current_room.player_1_stats.times is not None and current_room.player_2_stats.times is not None:
                        score_1_now = (await session.execute(
                            select(database.Users).where(database.Users.id == current_room.host))).scalar_one().points
                        score_2_now = (await session.execute(
                            select(database.Users).where(database.Users.id == current_room.other))).scalar_one().points
                        total_points = sum([utils.level_to_points(
                            x.level) for x in current_room.task_data])

                        score1new, score2new = utils.calculate_elo_rating(
                            score_1_now, score_2_now, current_room.player_1_stats.points / total_points,
                                                      current_room.player_2_stats.points / total_points)

                        t1 = [v for k, v in current_room.player_1_stats.times.items() if
                              k in current_room.player_1_stats.solved]
                        t2 = [v for k, v in current_room.player_2_stats.times.items() if
                              k in current_room.player_2_stats.solved]

                        await current_room.broadcast({
                            'event': 'scores',
                            'player1_new': score1new,
                            'player1_correct': len(current_room.player_1_stats.solved),
                            'player1_avgtime': sum(t1) / len(t1) if len(t1) > 0 else 0,
                            'player2_new': score2new,
                            'player2_correct': len(current_room.player_2_stats.solved),
                            'player2_avgtime': sum(t2) / len(t2) if len(t2) > 0 else 0,
                        })

                        battle_manager.remove_room(current_room)
=======
>>>>>>> 3a40817b830dbbd83c3c7fe90b7da7e9e721e5bc
                else:
                    await ws_error(websocket, f'Unknown command: {cmd}')

        except WebSocketDisconnect:
            if current_room and user_id:
                if current_room.status == 'started':
                    await current_room.broadcast({
                        'event': 'player_disconnected',
                        'user_id': user_id,
                        'message': 'Игрок отключился. Игра приостановлена.'
                    })
                    current_room.status = 'paused'

            connected_websockets.remove(websocket)
            break
        except json.JSONDecodeError:
            await ws_error(websocket, 'Incorrect JSON data')
        except Exception as e:
            print(f"Ошибка: {e}")
            await ws_error(websocket, f'Internal server error: {str(e)}')