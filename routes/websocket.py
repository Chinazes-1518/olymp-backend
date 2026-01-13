from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from utils import token_to_user
from battle import battle_manager, Room
import database


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
                    # room_id = battle_manager.add_room()
                    # await websocket.send_json({'room_id': r.id})

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.close(code=1008)  # Handle other exceptions gracefully
