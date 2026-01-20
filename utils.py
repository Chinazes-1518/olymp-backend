import hashlib
from uuid import uuid4
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException
from sqlalchemy import select, insert, update
from datetime import datetime
import json

import database
from database.database import Users


def json_response(data: dict) -> JSONResponse:
    return JSONResponse(jsonable_encoder(data), headers={
                        'Access-Control-Allow-Origin': '*'})


async def token_to_user(session, token: str) -> None:
    item = (await session.execute(select(database.Users).where(database.Users.token == token.strip()))).scalar_one_or_none()
    if item is None:
        return None
    else:
        return item


async def calculate_points(user_id: int, session, correct_answers: int, total_tasks: int, time_spent: list[int]) -> int:
    base_points = correct_answers * 10
    time_bonus = sum(max(0, 30 - t) for t in time_spent if t <= 30)
    accuracy_bonus = int((correct_answers / max(total_tasks, 1)) * 20)
    
    total_points = base_points + time_bonus + accuracy_bonus
    
    user = await session.execute(select(database.Users).where(database.Users.id == user_id))
    user = user.scalar_one_or_none()
    if user:
        await session.execute(
            update(database.Users)
            .where(database.Users.id == user_id)
            .values(points=database.Users.points + total_points)
        )
        await session.commit()
    
    return total_points


async def save_battle_history(session, room, player1_points, player2_points):
    await session.execute(
        insert(database.BattleHistory).values(
            id1=room.host,
            id2=room.other if room.other else room.host,
            result1=player1_points,
            result2=player2_points if room.other else 0,
            solvingtime1=room.game_state.player1_times if hasattr(room.game_state, 'player1_times') else [],
            solvingtime2=room.game_state.player2_times if hasattr(room.game_state, 'player2_times') and room.other else [],
            date=datetime.now()
        )
    )
    await session.commit()


def sanitize_task_data(task):
    return {
        'id': task.id,
        'level': task.level,
        'points': task.points,
        'category': task.category,
        'subcategory': task.subcategory,
        'condition': task.condition,
        'answer_type': task.answer_type
    }


async def get_user_by_id(session, user_id: int):
    user = await session.execute(select(database.Users).where(database.Users.id == user_id))
    return user.scalar_one_or_none()


async def get_user_room(session, user_id: int):
    from .battle import battle_manager
    return battle_manager.get_room_by_user(user_id)


async def check_room_access(session, user_id: int, room_id: int):
    from .battle import battle_manager
    room = battle_manager.get_room(room_id)
    if not room:
        return False, "Room not found"
    if user_id not in [room.host, room.other]:
        return False, "You are not in this room"
    return True, room


async def get_available_tasks(session, filters: dict):
    query = select(database.Tasks)
    
    if 'diff_start' in filters and 'diff_end' in filters:
        query = query.where(database.Tasks.level >= int(filters['diff_start']))
        query = query.where(database.Tasks.level <= int(filters['diff_end']))
    
    if 'cat' in filters:
        query = query.where(database.Tasks.category == filters['cat'])
    
    if 'subcat' in filters and filters['subcat']:
        from sqlalchemy import cast, String
        from sqlalchemy.dialects.postgresql import ARRAY
        query = query.where(
            cast(database.Tasks.subcategory, ARRAY(String)).op('&&')(filters['subcat'])
        )
    
    if 'count' in filters:
        from sqlalchemy import func
        query = query.order_by(func.random()).limit(int(filters['count']))
    
    result = await session.execute(query)
    return result.scalars().all()


async def end_game_early(session, room, reason: str = "Game ended early"):
    from .battle import battle_manager
    
    if room.game_state:
        room.game_state.status = "finished"
        
        await room.broadcast({
            'event': 'game_finished',
            'message': reason,
            'early': True
        })
    
    battle_manager.remove_room(room)


async def handle_player_disconnect(session, user_id: int, reason: str = "Player disconnected"):
    from .battle import battle_manager
    room = battle_manager.get_room_by_user(user_id)
    
    if room:
        other_user_id = room.other if user_id == room.host else room.host
        
        if other_user_id and room.game_state and room.game_state.status == "started":
            await end_game_early(session, room, f"{reason}. Game terminated.")
        else:
            await handle_player_leave(room, user_id)
    
    return room is not None


async def handle_player_leave(room, user_id: int):
    try:
        if user_id == room.host:
            if room.other_ws:
                await room.other_ws.send_json({
                    'event': 'room_deleted',
                    'reason': 'Room creator left'
                })
            from .battle import battle_manager
            battle_manager.remove_room(room)
        else:
            room.other = None
            room.other_ws = None
            
            if room.host_ws:
                await room.host_ws.send_json({
                    'event': 'player_left',
                    'player_id': user_id,
                    'message': 'Second player left the room'
                })
            
            from .battle import battle_manager
            if user_id in battle_manager.user_to_room:
                del battle_manager.user_to_room[user_id]
    except Exception as e:
        print(f"Error handling player leave: {e}")


def format_task_for_display(task):
    return {
        'id': task.id,
        'condition_preview': task.condition[:200] + "..." if len(task.condition) > 200 else task.condition,
        'level': task.level,
        'category': task.category,
        'subcategories': task.subcategory,
        'answer_type': task.answer_type
    }


def format_results_for_display(player1_data, player2_data, player1_correct, player2_correct, total_tasks, player1_points, player2_points):
    return {
        'player1': {
            'name': player1_data.name if player1_data else 'Player 1',
            'surname': player1_data.surname if player1_data else '',
            'correct_answers': player1_correct,
            'total_tasks': total_tasks,
            'percentage': int((player1_correct / total_tasks) * 100) if total_tasks > 0 else 0,
            'points': player1_points
        },
        'player2': {
            'name': player2_data.name if player2_data else 'Player 2',
            'surname': player2_data.surname if player2_data else '',
            'correct_answers': player2_correct,
            'total_tasks': total_tasks,
            'percentage': int((player2_correct / total_tasks) * 100) if total_tasks > 0 else 0,
            'points': player2_points
        }
    }


async def cleanup_empty_rooms():
    from .battle import battle_manager
    import time
    
    current_time = time.time()
    rooms_to_remove = []
    
    for room in battle_manager.rooms:
        if not room.host_ws or (hasattr(room.host_ws, 'client_state') and room.host_ws.client_state.name == 'DISCONNECTED'):
            rooms_to_remove.append(room)
        elif room.other and (not room.other_ws or (hasattr(room.other_ws, 'client_state') and room.other_ws.client_state.name == 'DISCONNECTED')):
            rooms_to_remove.append(room)
        elif room.game_state and room.game_state.status == "finished":
            if current_time - getattr(room.game_state, 'finish_time', current_time) > 30:
                rooms_to_remove.append(room)
    
    for room in rooms_to_remove:
        battle_manager.remove_room(room)
    
    return len(rooms_to_remove)


def create_error_response(message: str, code: int = 400):
    return {
        'event': 'error',
        'message': message,
        'code': code
    }


def create_success_response(event: str, data: dict = None):
    response = {'event': event}
    if data:
        response.update(data)
    return response


async def verify_websocket_message(data: dict) -> tuple[bool, str, dict]:
    if 'cmd' not in data:
        return False, "Missing 'cmd' field", {}
    
    if 'token' not in data:
        return False, "Missing 'token' field", {}
    
    return True, "", data


def format_room_data(room):
    return {
        'room_id': room.id,
        'name': room.name,
        'host': room.host,
        'other': room.other,
        'players_count': 2 if room.other else 1,
        'has_game': room.game_state is not None
    }


def format_game_state_data(game_state):
    if not game_state:
        return {'status': 'no_game'}
    
    return {
        'status': game_state.status,
        'current_task': game_state.current_task,
        'total_tasks': len(game_state.task_ids),
        'time_limit': game_state.time_limit,
        'player1_answers': game_state.player1_answers,
        'player2_answers': game_state.player2_answers,
        'player1_points': game_state.player1_points,
        'player2_points': game_state.player2_points
    }