from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, Header
from database.database import Tasks
from utils import json_response, token_to_user
import database
from typing import Annotated
import asyncio
import json
import time
from datetime import datetime


# class GameState:
#     def __init__(self, task_ids: list, time_limit: int):

#     def to_dict(self):
#         return {
#         }


class Room:
    def __init__(self, host: int, host_ws: WebSocket,
                 other: int | None, id: int, name: str) -> None:
        self.host = host
        self.host_ws = host_ws
        self.other = other
        self.other_ws: WebSocket | None = None
        self.id = id
        self.name = name
        # self.game_state: GameState | None = None
        self.task_data: list[Tasks] = []
        self.time_limit: int | None = None
        self.start_time: float | None = None
        self.player1_answers = {}
        self.player2_answers = {}
        self.player1_times = {}
        self.player2_times = {}
        self.player1_points = 0
        self.player2_points = 0
        self.status = "waiting"

    def json(self) -> dict:
        return {
            'host': self.host,
            'other': self.other,
            'id': self.id,
            'name': self.name,
            # 'game_state': self.game_state.to_dict() if self.game_state else None,
            # "time_limit": self.time_limit,
            # "player1_answers": self.player1_answers,
            # "player2_answers": self.player2_answers,
            # "player1_points": self.player1_points,
            # "player2_points": self.player2_points,
            # "status": self.status
        }
    
    async def broadcast(self, data: dict):
        if self.host_ws:
            await self.host_ws.send_json(data)
        if self.other_ws:
            await self.other_ws.send_json(data)


class BattleManager:
    def __init__(self) -> None:
        self.rooms: list[Room] = []
        self.id: int = 0
        self.user_to_room: dict[int, Room] = {}

    def add_room(self, host: int, host_ws: WebSocket, name: str) -> int:
        room = Room(host, host_ws, None, self.id, name)
        self.rooms.append(room)
        self.user_to_room[host] = room
        self.id += 1
        return self.id - 1

    def get_room(self, room_id: int) -> Room | None:
        for r in self.rooms:
            if r.id == room_id:
                return r
        return None

    def get_room_by_user(self, user_id: int) -> Room | None:
        return self.user_to_room.get(user_id)

    def get_rooms(self) -> list[Room]:
        return self.rooms

    def remove_room(self, room: Room):
        if room in self.rooms:
            self.rooms.remove(room)
            if room.host in self.user_to_room:
                del self.user_to_room[room.host]
            if room.other and room.other in self.user_to_room:
                del self.user_to_room[room.other]

    def user_join_room(self, user_id: int, room: Room, websocket: WebSocket):
        room.other = user_id
        room.other_ws = websocket
        self.user_to_room[user_id] = room


router = APIRouter(prefix='/battle')
battle_manager = BattleManager()


@router.get('/rooms')
async def get_rooms(token: Annotated[str, Header(alias="Authorization")]):
    async with database.sessions.begin() as session:
        if (await token_to_user(session, token)) is None:
            raise HTTPException(403, {"error": "Токен недействителен"})
        return json_response([x.json() for x in battle_manager.get_rooms()])


@router.get('/room')
async def get_room(
        token: Annotated[str, Header(alias="Authorization")], id: int):
    async with database.sessions.begin() as session:
        if (await token_to_user(session, token)) is None:
            raise HTTPException(403, {"error": "Токен недействителен"})
        r = battle_manager.get_room(id)
        if r is None:
            raise HTTPException(403, {"error": "Комната не найдена"})
        else:
            return json_response(r.json())
