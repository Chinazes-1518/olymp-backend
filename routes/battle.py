from __future__ import annotations
from asyncio import Task

from fastapi import APIRouter, HTTPException, WebSocket, Header, Depends
from fastapi.security import APIKeyHeader

from database.database import Tasks
from utils import json_response, token_to_user, user_by_id
import database
from typing import Annotated

API_Key_Header = APIKeyHeader(name='Authorization', auto_error=True)
class PlayerStats:
    def __init__(self) -> None:
        self.answers = {}
        self.times = None
        self.points = 0
        self.solved = []
        self.finished = False


class Room:
    def __init__(self, host: int, host_ws: WebSocket,
                 other: int | None, id: int, name: str) -> None:
        self.host = host
        self.host_ws = host_ws
        self.other = other
        self.other_ws: WebSocket | None = None
        self.id = id
        self.name = name
        self.task_data: list[Tasks] = []
        self.time_limit: int | None = None
        self.start_time: float | None = None
        self.player_1_stats = PlayerStats()  # host
        self.player_2_stats = PlayerStats()  # other
        self.status = "waiting"
        self.timer_task: Task | None = None
        self.category: int | None = None
        self.level_start: int | None = None
        self.level_end: int | None = None

    def json(self) -> dict:
        return {
            'host': self.host,
            'other': self.other,
            'id': self.id,
            'name': self.name,
            'time_limit': self.time_limit,
            'status': self.status,
            'count': len(self.task_data),
            'category': self.category,
            'level_start': self.level_start,
            'level_end': self.level_end,
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
        return self.user_to_room.get(user_id, None)

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
async def get_rooms(token: str=Depends(API_Key_Header)):
    async with database.sessions.begin() as session:
        if (await token_to_user(session, token)) is None:
            raise HTTPException(403, {"error": "Токен недействителен"})
        res = []
        for x in battle_manager.get_rooms():
            a = x.json()
            host_user = await user_by_id(session, x.host)
            a['host_name'] = f'{host_user.name} {host_user.surname[0]}.'
            if x.other:
                other_user = await user_by_id(session, x.other)
                a['other_name'] = f'{other_user.name} {other_user.surname[0]}.'
            res.append(a)
        return json_response(res)


@router.get('/room')
async def get_room(id: int,
        token: str=Depends(API_Key_Header)):
    async with database.sessions.begin() as session:
        if (await token_to_user(session, token)) is None:
            raise HTTPException(403, {"error": "Токен недействителен"})
        r = battle_manager.get_room(id)
        if r is None:
            raise HTTPException(403, {"error": "Комната не найдена"})
        else:
            return json_response(r.json())
