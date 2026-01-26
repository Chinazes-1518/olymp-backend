import asyncio
from time import sleep
from websockets.asyncio.client import connect
import json

async def send(websocket, data):
    await websocket.send(json.dumps(data))
    return json.loads(await websocket.recv())


async def hello():
    async with connect("ws://localhost:8000/ws") as ws:
        # await websocket.send(json.dumps({'cmd': 'create_room', 'token': 'faa92fd602b7bb83f4ba0f578b583d9f6182dd38f068ac4a', 'name': 'saslo'}))
        # message = await websocket.recv()
        # print(message)
        # room_id = json.loads(message)['room_id']
        # await websocket.send(json.dumps({'cmd': 'connect_to_room', 'token': '4f20444c8a86e5e738672ce68f9c94c88bba0e67fa74c067', 'room_id': room_id}))
        # message = await websocket.recv()
        # print(message)
        # await websocket.send(json.dumps({'cmd': 'start', 'token': 'faa92fd602b7bb83f4ba0f578b583d9f6182dd38f068ac4a', 'diff_start': 1, 'diff_end': 3, 'cat': 'geometry', 'subcat': ['triangles'], 'count': 2, 'time_limit': 1}))
        # message = await websocket.recv()
        # print(message)


        # token1 = '4f20444c8a86e5e738672ce68f9c94c88bba0e67fa74c067'
        # token2 = '0a430842d4ea7dc8412d6205fab981528515d5f59ae4ca65'
        # x = await send(ws, {
        #     'event': 'create_room',
        #     'token': token1,
        #     'name': 'test room'
        # })
        # print(x)
        # room = x['room_id']

        # x = await send(ws, {
        #     'event': 'join_room',
        #     'room_id': room,
        #     'token': token2
        # })
        # print(x)

        # x = await send(ws, {
        #     'event': 'start_game',
        #     'token': token2,
        #     'diff_start': 0,
        #     'diff_end': 10,
        #     'cat': 4,
        #     'subcat': [51, 84],
        #     'count': 5,
        #     'time_limit': 120
        # })

        print(await send(ws, {
            'event': 'create_room',
            'token': '7d138b15382bbe4ccbad43e4da6d582152eecbbf2b5351eb',
            'name': 'test'
        }))

        await asyncio.sleep(3)
        print(await ws.recv())

        print(await send(ws, {
            'event': 'leave_room',
            'token': '7d138b15382bbe4ccbad43e4da6d582152eecbbf2b5351eb',
        }))

        await asyncio.sleep(5)



if __name__ == "__main__":
    asyncio.run(hello())
