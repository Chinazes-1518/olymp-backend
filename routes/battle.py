from fastapi import APIRouter, HTTPException
from utils import json_response, token_to_user
import database


class Room():
    def __init__(self, host: int, other: int |
                 None, id: int, name: str) -> None:
        self.host = host
        self.other = other
        self.id = id
        self.name = name

    def json(self) -> dict:
        return {
            'host': self.host,
            'other': self.other,
            'id': self.id,
            'name': self.name,
        }


class BattleManager():
    def __init__(self) -> None:
        self.rooms: list[Room] = []
        self.id: int = 0

    def add_room(self, host: int, name: str) -> int:
        self.rooms.append(Room(host, None, self.id, name))
        self.id += 1
        return self.id - 1

    def get_room(self, room_id: int) -> Room | None:
        for r in self.rooms:
            if r.id == room_id:
                return r
        return None

    def get_rooms(self) -> list[Room]:
        return self.rooms


router = APIRouter(prefix='/battle')

battle_manager = BattleManager()


@router.get('/rooms')
async def get_rooms(token: str):
    async with database.sessions.begin() as session:
        if (await token_to_user(session, token)) is None:
            raise HTTPException(403, {"error": "Токен недействителен"})
        return json_response([x.json() for x in battle_manager.get_rooms()])


@router.get('/room')
async def get_rooms(token: str, id: int):
    async with database.sessions.begin() as session:
        if (await token_to_user(session, token)) is None:
            raise HTTPException(403, {"error": "Токен недействителен"})
        r = battle_manager.get_room(id)
        if r is None:
            raise HTTPException(403, {"error": "Комната не найдена"})
        else:
            return json_response(r.json())
