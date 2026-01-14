from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, insert, update, or_
from pydantic import BaseModel, constr
import database
import utils

router = APIRouter(prefix='/change')

@router.post('/points')


class Params(BaseModel):
    Userid: int
    points: int


async def add_points(data: Params) -> JSONResponse:
    async with database.sessions.begin() as session:
        request = await session.execute(select(database.Users).where(database.Users.id == data.Userid))
        user = request.scalar_one_or_none()
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if data.points is None or not isinstance(data, int) or data.points <= 0:
            raise HTTPException(400, {'error', 'Неверное значение очков'})
        user1 = session.query.get(data.Userid)
        if user1 is None:
            raise HTTPException(403, {'error': 'Пользователь не найден'})
        user1.points += data.points
        session.commit()
        return utils.json_response({'Userid': user1.Userid, 'new_points': user1.points})





