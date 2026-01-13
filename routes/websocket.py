from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from utils import token_to_id


router = APIRouter()


class Room():
    def __init__(self) -> None:
        self.host: int | None = None
        self.other: int | None = None
        self.id: int | None = None
        self.name: str | None = None


rooms: list[Room] = []


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

            user_id = await token_to_id(data['token'])
            if user_id is None:
                await websocket.send_json({'error': 'failed to verify token'})
                continue

            if data['cmd'] == 'create_room':
                if not verify_params(data, ['name']):
                    await websocket.send_json({'error': 'wrong params'})
                    continue
                r = Room()
                r.host = user_id
                r.id = len(rooms)
                r.name = data['name']
                rooms.append(r)
                await websocket.send_json({'room_id': r.id})
            elif 

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.close(code=1008)  # Handle other exceptions gracefully
