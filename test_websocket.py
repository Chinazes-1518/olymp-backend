import asyncio
from websockets.asyncio.client import connect
import json


async def hello():
    async with connect("ws://localhost:8000/ws") as websocket:
        await websocket.send(json.dumps({'cmd': 'create_room', 'token': 'faa92fd602b7bb83f4ba0f578b583d9f6182dd38f068ac4a', 'name': 'saslo'}))
        message = await websocket.recv()
        print(message)
        room_id = json.loads(message)['room_id']
        await websocket.send(json.dumps({'cmd': 'connect_to_room', 'token': '4f20444c8a86e5e738672ce68f9c94c88bba0e67fa74c067', 'room_id': room_id}))
        message = await websocket.recv()
        print(message)
        await websocket.send(json.dumps({'cmd': 'start', 'token': 'faa92fd602b7bb83f4ba0f578b583d9f6182dd38f068ac4a', 'diff_start': 1, 'diff_end': 3, 'cat': 'geometry', 'subcat': ['triangles'], 'count': 2, 'time_limit': 1}))
        message = await websocket.recv()
        print(message)


if __name__ == "__main__":
    asyncio.run(hello())
