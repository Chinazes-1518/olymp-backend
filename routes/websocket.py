from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, and_, cast, String, func, update
import asyncio
import json
import time
import sys

from routes import analytics
from utils import token_to_user
import utils
from .battle import battle_manager, Room
import database


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

    await asyncio.sleep(room.time_limit * 60)

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
                    # print(user_id, 'dbg 1')
                    if current_room is not None:
                        # print(user_id, 'dbg 2')
                        if current_room.host == user_id:
                            # print(user_id, 'dbg 3')
                            current_room.host_ws = websocket
                        elif current_room.other == user_id:
                            # print(user_id, 'dbg 4')
                            current_room.other_ws = websocket

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

                    tasks_data = await utils.filter_tasks(session, level_start, level_end, subcategory, None, category, True, count)

                    current_room.task_data = tasks_data
                    print(current_room.task_data)
                    current_room.total_points = sum([utils.level_to_points(x['level']) for x in current_room.task_data])
                    current_room.player_1_stats.correct = [False] * len(tasks_data)
                    current_room.player_2_stats.correct = [False] * len(tasks_data)

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

                    await room.host_ws.send_json({
                        'event': 'player_joined',
                        'user_id': user_id,
                        'name': f'{user.name} {user.surname[0]}.'
                    })

                    await websocket.send_json({
                        'event': 'join_successful'
                    })
                elif cmd == 'leave_room':
                    if current_room:
                        if user_id == current_room.host:
                            await broadcast({
                                'event': 'room_deleted',
                                'room_id': current_room.id
                            })
                            battle_manager.remove_room(current_room)
                        else:
                            current_room.other = None
                            current_room.other_ws = None

                            await broadcast({
                                'event': 'player_left',
                                'room_id': current_room.id,
                            })

                            if user_id in battle_manager.user_to_room:
                                del battle_manager.user_to_room[user_id]
                        current_room = None

                        await websocket.send_json({
                            'event': 'leave_successful',
                        })
                    else:
                        await ws_error(websocket, 'not in a room')
                        continue
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

                    current_room.timer_task = asyncio.create_task(start_game_timer(current_room))
                elif cmd == 'send_answer':
                    if not verify_params(data, ['answer', 'time']):
                        await ws_error(websocket, 'Wrong params')
                        continue

                    if current_room is None or current_room.status != 'started':
                        await ws_error(websocket, 'Not in game')
                        continue

                    task = (await session.execute(select(database.Tasks).where(database.Tasks.id == int(current_room.task_data[current_room.current_task]['id'])))).scalar_one_or_none()
                    if task is None:
                        await ws_error(websocket, 'Task not found')
                        continue

                    correct = utils.gigachat_check_answer(data['answer'].strip(), task.condition, task.answer).lower() == 'да'
                    if user_id == current_room.host:
                        if current_room.player_1_stats.answered:
                            await ws_error(websocket, 'Task already solved')
                            continue
                        current_room.player_1_stats.times.append(int(data['time']))
                        current_room.player_1_stats.answered = True
                    else:
                        if current_room.player_2_stats.answered:
                            await ws_error(websocket, 'Task already solved')
                            continue
                        current_room.player_2_stats.times.append(int(data['time']))
                        current_room.player_2_stats.answered = True
                    if correct:
                        if user_id == current_room.host:  # player 1
                            current_room.player_1_stats.correct[current_room.current_task] = True
                            current_room.player_1_stats.points += utils.level_to_points(
                                task.level)
                            await current_room.other_ws.send_json({'event': 'other_solved', 'total_points': current_room.player_1_stats.points})
                        else:  # player 2
                            current_room.player_2_stats.correct[current_room.current_task] = True
                            current_room.player_2_stats.points += utils.level_to_points(
                                task.level)
                            await current_room.host_ws.send_json({'event': 'other_solved', 'total_points': current_room.player_2_stats.points})
                        await websocket.send_json({'event': 'check_result', 'correct': True, 'points': utils.level_to_points(task.level)})
                    else:
                        await websocket.send_json({'event': 'check_result', 'correct': False})

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

                            t1 = [x for i, x in enumerate(current_room.player_1_stats.times) if current_room.player_1_stats.correct[i]]
                            t2 = [x for i, x in enumerate(current_room.player_2_stats.times) if current_room.player_2_stats.correct[i]]

                            await current_room.broadcast({
                                'event': 'scores',
                                'player1_new': score1new,
                                'player1_correct': sum(current_room.player_1_stats.correct),
                                'player1_avgtime': sum(t1) / len(t1) if len(t1) > 0 else 0,
                                'player2_new': score2new,
                                'player2_correct': sum(current_room.player_2_stats.correct),
                                'player2_avgtime': sum(t2) / len(t2) if len(t2) > 0 else 0,
                            })

                            await session.execute(update(database.Users).where(database.Users.id == current_room.host).values(status=None, score=score1new))
                            await session.execute(update(database.Users).where(database.Users.id == current_room.other).values(status=None, score=score2new))
                            await session.commit()

                            await analytics.change_values(current_room.host, {'task_quantity': len(current_room.task_data), 'answer_quantity': len(current_room.task_data), 'time_per_task': {
                                current_room.task_data[i]['id']: current_room.player_1_stats.times[i] for i in range(len(current_room.task_data)) if current_room.player_1_stats.correct[i]
                            }})
                            await analytics.change_values(current_room.other, {'task_quantity': len(current_room.task_data), 'answer_quantity': len(current_room.task_data), 'time_per_task': {
                                current_room.task_data[i]['id']: current_room.player_2_stats.times[i] for i in range(len(current_room.task_data)) if current_room.player_2_stats.correct[i]
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
                    if current_room.status != 'started':
                        await ws_error(websocket, 'Room is not running')
                        continue
                    res = current_room.json()
                    if user_id == current_room.host:
                        other_user = await utils.user_by_id(session, current_room.other)
                        res |= {
                            'correct': current_room.player_1_stats.correct,
                            'points': current_room.player_1_stats.points,
                            'other_points': current_room.player_2_stats.points,
                            'answered': current_room.player_1_stats.answered,
                            'finished': current_room.player_1_stats.finished,
                            'times': current_room.player_1_stats.times,
                        }
                    else:
                        other_user = await utils.user_by_id(session, current_room.host)
                        res |= {
                            'correct': current_room.player_2_stats.correct,
                            'points': current_room.player_2_stats.points,
                            'other_points': current_room.player_1_stats.points,
                            'answered': current_room.player_2_stats.answered,
                            'finished': current_room.player_2_stats.finished,
                            'times': current_room.player_2_stats.times,
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
                    res['other_name'] = f'{other_user.name} {other_user.surname[0]}.'
                    res['start_time'] = current_room.start_time
                    await websocket.send_json(res)
                else:
                    await ws_error(websocket, f'Unknown command: {cmd}')
        except WebSocketDisconnect:
            # if current_room and user_id:
            #     await handle_player_leave(current_room, user_id)
            print(f"Игрок {user_id} отключился")
            connected_websockets.remove(websocket)
            break
        except json.JSONDecodeError:
            await ws_error(websocket, 'Incorrect JSON data')
        except Exception as e:
            print(f"Ошибка: {e.with_traceback()}")
            await ws_error(websocket, f'Internal server error: {str(e)}')
