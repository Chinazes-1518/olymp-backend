from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select, insert, update, or_
from pydantic import BaseModel, constr
import database
import utils
from typing import Annotated

router = APIRouter(prefix='/change')

@router.post('/points')



async def add_points(points: Annotated[str, Query()],
                   token: Annotated[str, Header(alias='Authorization')]) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if points is None or not isinstance(points, int) or points <= 0:
            raise HTTPException(400, {'error', 'Неверное значение очков'})
        user1 = session.query.get(user.id)
        user1.points += points
        session.commit()
        return utils.json_response({'Userid': user1.Userid, 'new_points': user1.points})





