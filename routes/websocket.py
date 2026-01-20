from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, and_, cast, String, func
from sqlalchemy.dialects.postgresql import ARRAY
import asyncio
import json
import time

from utils import token_to_user, calculate_points, save_battle_history, get_user_by_id
from .battle import battle_manager, Room, GameState
import database
from database import Tasks


router = APIRouter()


def verify_params(data: dict, params: list[str]) -> bool:
    return all(x in data for x in params)


async def start_game_timer(room: Room):
    try:
        if not room.game_state:
            return

        game_state = room.game_state
        game_state.start_game()

        await room.broadcast({
            'event': 'игра началась',
            'задача': game_state.get_current_task_data(),
            'всего_задач': len(game_state.task_ids),
            'лимит_времени': game_state.time_limit
        })

        task_duration = game_state.time_limit * 60
        start_time = time.time()

        while time.time() - start_time < task_duration:
            if game_state.status != "started":
                break

            elapsed = int(time.time() - start_time)
            remaining = max(0, task_duration - elapsed)

            await room.broadcast({
                'event': 'обновление времени',
                'прошло_секунд': elapsed,
                'осталось_секунд': remaining,
                'номер_задачи': game_state.current_task
            })

            if game_state.check_both_answered():
                await handle_task_completion(room)

            await asyncio.sleep(1)

        if game_state.status == "started":
            await room.broadcast({
                'event': 'время вышло',
                'номер_задачи': game_state.current_task
            })
            await asyncio.sleep(2)
            await handle_task_completion(room)

    except Exception as e:
        print(f"Ошибка таймера игры: {e}")


async def handle_task_completion(room: Room):
    game_state = room.game_state

    if game_state.current_task >= len(room.tasks_data):
        return

    correct_answer = room.tasks_data[game_state.current_task].answer

    player1_answer = game_state.player1_answers.get(
        game_state.current_task, "")
    player2_answer = game_state.player2_answers.get(
        game_state.current_task, "")

    player1_correct = player1_answer.strip().lower() == correct_answer.strip().lower()
    player2_correct = player2_answer.strip().lower() == correct_answer.strip().lower()

    await room.broadcast({
        'event': 'результат задачи',
        'номер_задачи': game_state.current_task,
        'правильный_ответ': correct_answer,
        'игрок1_ответ': player1_answer,
        'игрок2_ответ': player2_answer,
        'игрок1_правильно': player1_correct,
        'игрок2_правильно': player2_correct,
        'игрок1_время': game_state.player1_times.get(game_state.current_task, 0),
        'игрок2_время': game_state.player2_times.get(game_state.current_task, 0)
    })

    if game_state.next_task():
        await asyncio.sleep(3)

        await room.broadcast({
            'event': 'отсчет времени',
            'секунд': 3,
            'сообщение': 'Следующее задание через'
        })

        for i in range(3, 0, -1):
            await room.broadcast({
                'event': 'отсчет времени',
                'секунд': i,
                'сообщение': f'Начало через {i}...'
            })
            await asyncio.sleep(1)

        await room.broadcast({
            'event': 'задачи выбраны',
            'задача': game_state.get_current_task_data(),
            'номер_задачи': game_state.current_task,
            'всего_задач': len(game_state.task_ids)
        })

        asyncio.create_task(start_game_timer(room))
    else:
        await finish_game(room)


async def finish_game(room: Room):
    game_state = room.game_state
    game_state.status = "finished"

    player1_correct, player2_correct = game_state.calculate_final_points()

    async with database.sessions.begin() as session:
        player1_data = await get_user_by_id(session, room.host)
        player2_data = await get_user_by_id(session, room.other) if room.other else None

        player1_times = [game_state.player1_times.get(
            i, 0) for i in range(len(game_state.task_ids))]
        player1_points = await calculate_points(
            room.host, session,
            player1_correct, len(game_state.task_ids), player1_times
        )

        player2_points = 0
        if room.other:
            player2_times = [game_state.player2_times.get(
                i, 0) for i in range(len(game_state.task_ids))]
            player2_points = await calculate_points(
                room.other, session,
                player2_correct, len(game_state.task_ids), player2_times
            )

        await save_battle_history(session, room, player1_points, player2_points)

        if player1_correct > player2_correct:
            winner = player1_data.name if player1_data else "Игрок 1"
        elif player2_correct > player1_correct:
            winner = player2_data.name if player2_data else "Игрок 2"
        else:
            winner = "Ничья"

        await room.broadcast({
            'event': 'игра завершена',
            'сообщение': 'Игра завершена!'
        })

        await room.broadcast({
            'event': 'итоговые результаты',
            'результаты': {
                'игрок1': {
                    'имя': player1_data.name if player1_data else 'Игрок 1',
                    'фамилия': player1_data.surname if player1_data else '',
                    'правильные_ответы': player1_correct,
                    'всего_задач': len(game_state.task_ids),
                    'очки': player1_points
                },
                'игрок2': {
                    'имя': player2_data.name if player2_data else 'Игрок 2',
                    'фамилия': player2_data.surname if player2_data else '',
                    'правильные_ответы': player2_correct,
                    'всего_задач': len(game_state.task_ids),
                    'очки': player2_points if room.other else 0
                },
                'победитель': winner
            }
        })

        await asyncio.sleep(10)
        battle_manager.remove_room(room)


async def handle_player_leave(room: Room, user_id: int):
    try:
        if user_id == room.host:
            if room.other_ws:
                await room.other_ws.send_json({
                    'event': 'room_deleted',
                    'reason': 'Host left'
                })
            battle_manager.remove_room(room)
        else:
            room.other = None
            room.other_ws = None

            if room.host_ws:
                await room.host_ws.send_json({
                    'event': 'player_left',
                    'user_id': user_id,
                })

            if user_id in battle_manager.user_to_room:
                del battle_manager.user_to_room[user_id]
    except Exception as e:
        print(f"Ошибка при выходе игрока: {e}")

connected_websockets: list[WebSocket] = []


async def broadcast(data: dict) -> None:
    for s in connected_websockets:
        await s.send_json(data)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = None
    current_room = None
<<<<<<< HEAD
    try:
        while True:
=======
    connected_websockets.append(websocket)

    while True:
        try:
>>>>>>> 7c9a1737b747fccfb8b0c611b59636bba0cf9357
            data = await websocket.receive_json()

            if 'event' not in data or 'token' not in data:
                await websocket.send_json({
                    'event': 'error',
                    'message': 'specify event and token'
                })
                continue

            async with database.sessions.begin() as session:
                user = await token_to_user(session, data['token'])
                if user is None:
                    await websocket.send_json({
                        'event': 'error',
                        'message': 'Failed to verify token'
                    })
                    continue

                user_id = user.id
                cmd = data['event']

                if cmd == 'create_room':
                    if not verify_params(data, ['name']):
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'Specify room name'
                        })
                        continue

                    existing_room = battle_manager.get_room_by_user(user_id)
                    if existing_room:
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'You are already in a room'
                        })
                        continue

                    room_id = battle_manager.add_room(
                        user_id, websocket, data['name'])
                    current_room = battle_manager.get_room(room_id)

                    await websocket.send_json({
                        'event': 'your_room_created',
                        'room_id': room_id,
                    })
                    await broadcast({
                        'event': 'room_created',
                        'host': user_id,
                        'id': room_id,
                        'name': data['name']
                    })
                elif cmd == 'join_room':
                    if not verify_params(data, ['room_id']):
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'Specify room id'
                        })
                        continue

                    room = battle_manager.get_room(int(data['room_id']))
                    if room is None:
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'Room not found'
                        })
                        continue

                    if room.other is not None:
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'Room is already full'
                        })
                        continue

                    if user_id == room.host:
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'You are the host'
                        })
                        continue

                    battle_manager.user_join_room(user_id, room, websocket)
                    current_room = room

                    await room.host_ws.send_json({
                        'event': 'player_joined',
                        'user_id': user_id,
                        'name': user.name,
                    })

                    await websocket.send_json({
                        'event': 'join_succesful'
                    })
                elif cmd == 'leave_room':
                    if current_room:
                        await handle_player_leave(current_room, user_id)
                        current_room = None

                    await websocket.send_json({
                        'event': 'leave_succesful',
                    })
                elif cmd == 'start_game':
                    required_params = [
                        'diff_start',
                        'diff_end',
                        'cat',
                        'subcat',
                        'count',
                        'time_limit']
                    if not verify_params(data, required_params):
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'Parameters not found'
                        })
                        continue

                    room = battle_manager.get_room_by_user(user_id)
                    if room is None:
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'You are not in a room'
                        })
                        continue

                    if user_id != room.host:
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'Only host can start game'
                        })
                        continue

                    if room.other is None:
                        await websocket.send_json({
                            'event': 'error',
                            'message': 'Room is not full yet'
                        })
                        continue

                    tasks = list((await session.execute(select(Tasks).where(
                        and_(
                            Tasks.level >= int(data['diff_start']),
                            Tasks.level <= int(data['diff_end']),
                            Tasks.category == data['cat'],
                            cast(
                                Tasks.subcategory,
                                ARRAY(String)).op('&&')(
                                data['subcat'])
                        )
                    ).order_by(func.random()).limit(int(data['count'])))).scalars().all())

                    if len(tasks) < int(data['count']):
                        await websocket.send_json({
                            'event': 'error',
                            'message': f'Found {len(tasks)} tasks for given criteria'
                        })
                        continue

                    room.task_data = tasks
                    room.game_state = GameState(
                        [t.id for t in tasks],
                        int(data['time_limit']),
                        tasks
                    )

                    await room.broadcast({
                        'event': 'tasks_selected',
                        'tasks': t
                    })

                    await room.broadcast({
                        'event': 'отсчет времени',
                        'секунд': 5,
                        'сообщение': 'Игра начнется через'
                    })

                    for i in range(5, 0, -1):
                        await room.broadcast({
                            'event': 'отсчет времени',
                            'секунд': i,
                            'сообщение': f'Начало через {i}...'
                        })
                        await asyncio.sleep(1)

                    asyncio.create_task(start_game_timer(room))

                elif cmd == 'отправить ответ':
                    if not verify_params(data, ['answer']):
                        await websocket.send_json({
                            'event': 'ошибка',
                            'сообщение': 'Отсутствует ответ'
                        })
                        continue

                    room = battle_manager.get_room_by_user(user_id)
                    if room is None or room.game_state is None:
                        await websocket.send_json({
                            'event': 'ошибка',
                            'сообщение': 'Вы не в игре'
                        })
                        continue

                    if room.game_state.status != "started":
                        await websocket.send_json({
                            'event': 'ошибка',
                            'сообщение': 'Игра еще не началась или уже завершена'
                        })
                        continue

                    player = "player1" if user_id == room.host else "player2"

                    is_correct, time_spent = room.game_state.submit_answer(
                        player,
                        data['answer']
                    )

                    if is_correct:
                        await websocket.send_json({
                            'event': 'ответ правильный',
                            'номер_задачи': room.game_state.current_task,
                            'затраченное_время': time_spent
                        })
                    else:
                        await websocket.send_json({
                            'event': 'ответ неправильный',
                            'номер_задачи': room.game_state.current_task,
                            'затраченное_время': time_spent
                        })

                    other_user_id = room.other if user_id == room.host else room.host
                    await room.send_to_user(other_user_id, {
                        'event': 'ответ получен',
                        'игрок': player,
                        'номер_задачи': room.game_state.current_task
                    })

                elif cmd == 'отправить сообщение в чат':
                    if not verify_params(data, ['message']):
                        await websocket.send_json({
                            'event': 'ошибка',
                            'сообщение': 'Отсутствует текст сообщения'
                        })
                        continue

                    room = battle_manager.get_room_by_user(user_id)
                    if room is None:
                        await websocket.send_json({
                            'event': 'ошибка',
                            'сообщение': 'Вы не в комнате'
                        })
                        continue

                    user_data = await get_user_by_id(session, user_id)
                    username = f"{user_data.name} {user_data.surname}" if user_data else "Игрок"

                    await room.broadcast({
                        'event': 'сообщение чата',
                        'от': username,
                        'сообщение': data['message'],
                        'время': time.strftime("%H:%M:%S")
                    })

                elif cmd == 'запросить состояние игры':
                    room = battle_manager.get_room_by_user(user_id)
                    if room is None or room.game_state is None:
                        await websocket.send_json({
                            'event': 'состояние игры',
                            'статус': 'нет активной игры',
                            'в_комнате': room is not None
                        })
                        continue

                    await websocket.send_json({
                        'event': 'состояние игры',
                        'статус': room.game_state.status,
                        'номер_текущей_задачи': room.game_state.current_task,
                        'всего_задач': len(room.game_state.task_ids),
                        'время_на_задачу': room.game_state.time_limit,
                        'ответы_игрока1': room.game_state.player1_answers,
                        'ответы_игрока2': room.game_state.player2_answers,
                        'очки_игрока1': room.game_state.player1_points,
                        'очки_игрока2': room.game_state.player2_points
                    })

                elif cmd == 'изменить статус готовности':
                    if not verify_params(data, ['ready']):
                        await websocket.send_json({
                            'event': 'ошибка',
                            'сообщение': 'Отсутствует статус готовности'
                        })
                        continue

                    room = battle_manager.get_room_by_user(user_id)
                    if room is None:
                        await websocket.send_json({
                            'event': 'ошибка',
                            'сообщение': 'Вы не в комнате'
                        })
                        continue

                    player_key = 'host' if user_id == room.host else 'other'

                    other_user_id = room.other if user_id == room.host else room.host
                    if other_user_id:
                        status_text = "готов" if data['ready'] else "не готов"
                        await room.send_to_user(other_user_id, {
                            'event': 'статус игрока',
                            'игрок_id': user_id,
                            'статус': status_text
                        })

                    await websocket.send_json({
                        'event': 'статус игрока',
                        'ваш_статус': "готов" if data['ready'] else "не готов"
                    })

                else:
                    await websocket.send_json({
                        'event': 'ошибка',
                        'сообщение': f'Неизвестная команда: {cmd}'
                    })
        except WebSocketDisconnect:
            if current_room and user_id:
                await handle_player_leave(current_room, user_id)
            print(f"Игрок {user_id} отключился")
            connected_websockets.remove(websocket)
            break
        except json.JSONDecodeError:
            await websocket.send_json({
                'event': 'ошибка',
                'сообщение': 'Некорректный JSON формат'
            })
        except Exception as e:
            print(f"Ошибка: {e}")
            await websocket.send_json({
                'event': 'ошибка',
                'сообщение': f'Внутренняя ошибка сервера: {str(e)}'
            })
