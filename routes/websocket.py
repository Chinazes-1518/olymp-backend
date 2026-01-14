from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, and_, cast, String, func
from sqlalchemy.dialects.postgresql import ARRAY

from utils import token_to_user
from .battle import battle_manager, Room
import database
from database import Tasks


router = APIRouter()


def verify_params(data: dict, params: list[str]) -> bool:
    return all(x in data for x in params)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()

            if 'cmd' not in data or 'token' not in data:
                await websocket.send_json({'error': 'wrong params'})
                continue

            async with database.sessions.begin() as session:
                user = await token_to_user(session, data['token'])
                if user is None:
                    await websocket.send_json({'error': 'failed to verify token'})
                    continue
                user_id = user.id

                if data['cmd'] == 'create_room':
                    if not verify_params(data, ['name']):
                        await websocket.send_json({'error': 'wrong params'})
                        continue
                    room_id = battle_manager.add_room(
                        user_id, websocket, data['name'])
                    await websocket.send_json({'room_id': room_id})
                    continue
                elif data['cmd'] == 'connect_to_room':
                    if not verify_params(data, ['room_id']):
                        await websocket.send_json({'error': 'wrong params'})
                        continue
                    room = battle_manager.get_room(int(data['room_id']))
                    if room is None:
                        await websocket.send_json({'error': 'room not found'})
                        continue
                    else:
                        room.other = user_id
                        room.other_ws = websocket
                        await websocket.send_json(room.json())
                        continue
                elif data['cmd'] == 'leave_room':
                    for r in battle_manager.get_rooms():
                        if r.host == user_id:
                            if r.other_ws is not None:
                                await r.other_ws.send_json({'cmd': 'room_deleted'})
                            battle_manager.get_rooms().remove(r)
                            break
                        if r.other == user_id:
                            await r.host_ws.send_json({'cmd': 'other_left'})
                            r.other = None
                            r.other_ws = None
                            break
                    continue
                elif data['cmd'] == 'start':
                    if not verify_params(
                            data, ['diff_start', 'diff_end', 'cat', 'subcat', 'count', 'time_limit']):
                        await websocket.send_json({'error': 'wrong params'})
                        continue
                    r = battle_manager.get_room_by_user(user_id)
                    if r is None:
                        await websocket.send_json({'error': 'room not found'})
                        continue
                    if user_id != r.host:
                        await websocket.send_json({'error': 'only host can start'})
                        continue
                    t = (await session.execute(select(Tasks).where(
                        and_(
                            Tasks.level >= int(data['diff_start']),
                            Tasks.level <= int(data['diff_end']),
                            Tasks.category == data['cat'],
                            cast(
                                Tasks.subcategory,
                                ARRAY(String)).op('&&')(
                                data['subcat'])
                        )
                    ).order_by(func.random()).limit(int(data['count'])))).scalars().all()
                    await websocket.send_json([[x.id, x.level, x.points, x.category, x.subcategory] for x in t])
                    continue

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_json({'error': str(e)})
