from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
import uvicorn
import asyncio

import database
import routes
import utils


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating tables in database")
    async with database.engine.begin() as connection:
        await connection.run_sync(database.MainBase.metadata.create_all)
    await routes.analytics.change_values({'task_quantity': 3, 'answer_quantity': 5, 'time_per_task': {'123456': 180}})
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(routes.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# class ConnectionManager:
#     def __init__(self):
#         self.active_connections = {}
#         self.waiting_users = []
#         self.active_matches = {}
    
#     async def connect(self, websocket: WebSocket, user_id: int):
#         await websocket.accept()
#         self.active_connections[user_id] = websocket
    
#     def disconnect(self, user_id: int):
#         if user_id in self.active_connections:
#             del self.active_connections[user_id]
    
#     async def send_message(self, user_id: int, message: dict):
#         import json
#         if user_id in self.active_connections:
#             await self.active_connections[user_id].send_text(json.dumps(message))
    
#     async def broadcast(self, message: dict):
#         import json
#         for connection in self.active_connections.values():
#             await connection.send_text(json.dumps(message))

# manager = ConnectionManager()

# @app.websocket("/ws/pvp")
# async def websocket_endpoint(websocket: WebSocket, token: str = ""):
#     if not token:
#         await websocket.close(code=1008, reason="")
#         return
    
#     try:
#         from utils import verify_jwt_token
#         payload = verify_jwt_token(token)
#         user_id = payload.get("user_id")
        
#         if not user_id:
#             await websocket.close(code=1008, reason="saslochupep8")
#             return
        
#         await manager.connect(websocket, user_id)
        
#         try:
#             while True:
#                 data = await websocket.receive_text()
#                 import json
#                 message = json.loads(data)
#                 await handle_websocket_message(user_id, message)
#         except WebSocketDisconnect:
#             manager.disconnect(user_id)
            
#     except Exception as e:
#         await websocket.close(code=1008, reason=str(e))
# async def handle_websocket_message(user_id: int, message: dict):
#     message_type = message.get("type")

# uvicorn.run(app, port=8000, reload=True)
if __name__ == "__main__":
    uvicorn.run("__main__:app", host="0.0.0.0", port=8000, reload=True, workers=2)
