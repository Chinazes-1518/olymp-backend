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


class UserInfo(BaseModel):
    token: str
    Userid: int


@router.post('/statistics')
async def get_statistics(data: UserInfo) -> JSONResponse:
    async with database.sessions.begin() as session:
        request = await session.execute(select(database.Users).where(database.Users.id == data.Userid))
        user = request.scalar_one_or_none()
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if data.token != user.token:
            raise HTTPException(403, {'error': 'Неверный токен'})
        if user.role == 'administrator':
            request = await session.execute(select(database.BattleHistory))
            history = request.skalars().all()
            return utils.json_response({'history': history})
        else:
            request = await session.execute(select(database.BattleHistory)
                                            .where(
                or_(database.BattleHistory.id1 == data.Userid, database.BattleHistory.id2 == data.Userid)))
            history = request.scalars().all()
            return utils.json_response({'history': history})


class Task(BaseModel):
    token: str
    Userid: int
    level: int
    points: int
    category: str
    subcategory: list[str]
    condition: str
    solution: str
    answer: str
    source: str
    answer_type: str


@router.post('/import_task')
async def import_task(data: Task) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, data[0].token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            await import_tasks_to_db([data])
        else:
            raise HTTPException(403, {'error': 'Импортировать задачи может только администратор!'})


@router.post('/import_tasks')
async def import_tasks(data: list[Task]) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, data[0].token)
        if user is None:
            raise HTTPException(403, {'error': "Неверный токен"})
        if user.role == 'administrator':
            await import_tasks_to_db(data)
        else:
            raise HTTPException(403, {'error': 'Импортировать задачи может только администратор!'})


@router.post('/export_tasks')
async def export_tasks(data: UserInfo) -> JSONResponse:
    async with database.sessions.begin() as session:
        request = await session.execute(select(database.Users).where(database.Users.id == data.Userid))
        user = request.scalar_one_or_none()
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if data.token != user.token:
            raise HTTPException(403, {'error': 'Неверный токен'})
        if user.role == 'administrator':
            request = await session.execute(select(database.Tasks))
            tasks = request.scalars().all()
            tasks_data = [{"id": item.id,
                           'level': item.level,
                           'points': item.points,
                           'category': item.category,
                           'subcategory': ''.join(item.subcategory),
                           'condition': item.condition,
                           'solution': item.solution,
                           'answer': item.answer,
                           'source': item.source,
                           'answer_type': item.answer_type,
                           } for item in tasks]
            return utils.json_response({'tasks': tasks_data})
        else:
            raise HTTPException(403, {'error': ' Экспортировать задачи может только администратор!'})


async def import_tasks_to_db(data):
    async with database.sessions.begin() as session:
        await session.execute(insert(database.Tasks), data)
        await session.commit()
