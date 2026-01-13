from fastapi import APIRouter, HTTPException
from utils import verify_token


class Room():
    def __init__(self, host: int, other: int |
                 None, id: int, name: str) -> None:
        self.host = host
        self.other = other
        self.id = id
        self.name = name


class BattleManager():
    def __init__(self) -> None:
        self.rooms: list[Room] = []
        self.id: int = 0

    def add_room(self, host: int, name: str) -> int:
        self.rooms.append(Room(host, None, self.id, name))
        self.id += 1
        return self.id - 1


router = APIRouter(prefix='/battle')

battle_manager = BattleManager


@router.get('/rooms')
async def get_rooms(token: str):
    if not (await verify_token(token)):
        raise HTTPException(403, {"error": "Токен недействителен"})
