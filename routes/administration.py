import hashlib
from uuid import uuid4

from fastapi import APIRouter, HTTPException, FastAPI, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select, insert, update, or_
from pydantic import BaseModel, constr
from sqlalchemy.util import greenlet_spawn

import database
import secrets
import utils
from database import BattleHistory

router = APIRouter(prefix='/admin')


class Statistics(BaseModel):
    token: constr(min_length=3, max_length=100)
    Userid: constr(min_length=3, max_length=50)


@router.get('/statistics')
async def get_statistics(authorization: Statistics) -> JSONResponse:
    async with database.sessions.begin() as session:
          request = await session.execute(select(database.Users).where(database.Users.id == authorization.id))
          user = request.scalar_one_or_none()
          if user is None:
               raise HTTPException(403, {'error': 'Пользователь не существует'})
          if authorization.token != user.token:
              raise HTTPException(403, {'error': 'Неверный токен'})
          if user.role == 'administrator':
               request = await session.execute(select(database.BattleHistory))
               history = request.skalars().all()
               return utils.json_responce({'history': history})
          else:
               request = await session.execute(select(database.BattleHistory)
                                               .where(or_(database.BattleHistory.id1 == authorization.id, database.BattleHistory.id2 == authorization.id)))
               history = request.skalars().all()
               return utils.json_responce({'history': history})


















