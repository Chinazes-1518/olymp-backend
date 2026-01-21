import hashlib
from uuid import uuid4

from fastapi import APIRouter, HTTPException, FastAPI, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, insert, update, or_, and_
from pydantic import BaseModel, constr
from sqlalchemy.util import greenlet_spawn
from typing import Annotated

import database
import utils

router = APIRouter(prefix='/admin')


@router.post('/statistics')
async def get_statistics(token: Annotated[str, Header(
        alias='Authorization')]) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            request = await session.execute(select(database.BattleHistory))
            history = request.skalars().all()
            return utils.json_response({'history': history})
        else:
            request = await session.execute(select(database.BattleHistory)
                                            .where(
                or_(database.BattleHistory.id1 == user.id, database.BattleHistory.id2 == user.id)))
            history = request.scalars().all()
            return utils.json_response({'history': history})


class Task(BaseModel):
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
async def import_task(data: Task, token: Annotated[str, Header(
        alias="Authorization")]) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            await import_tasks_to_db([data])
        else:
            raise HTTPException(
                403, {
                    'error': 'Импортировать задачи может только администратор!'})


@router.post('/import_tasks')
async def import_tasks(data: list[Task], token: Annotated[str, Header(
        alias="Authorization")]) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': "Неверный токен"})
        if user.role == 'administrator':
            await import_tasks_to_db(data)
        else:
            raise HTTPException(
                403, {
                    'error': 'Импортировать задачи может только администратор!'})


@router.post('/export_tasks')
async def export_tasks(token: Annotated[str, Header(
        alias="Authorization")]) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            request = await session.execute(select(database.Tasks))
            tasks = request.scalars().all()
            tasks_data = [{"id": item.id,
                           'level': item.level,
                           'category': item.category,
                           'subcategory': ';'.join(item.subcategory),
                           'condition': item.condition,
                           'solution': item.solution,
                           'answer': item.answer,
                           'source': item.source,
                           'answer_type': item.answer_type,
                           } for item in tasks]
            return utils.json_response({'tasks': tasks_data})
        else:
            raise HTTPException(
                403, {
                    'error': ' Экспортировать задачи может только администратор!'})


async def import_tasks_to_db(data):
    async with database.sessions.begin() as session:
        cat = (await session.execute(select(database.Categories).where(database.Categories.name == data['category']))).scalar_one_or_none()
        if cat is None:
            cat_id = (await session.execute(insert(database.Categories).values(name=data['category']))).inserted_primary_key[0]
        else:
            cat_id = cat.id
        subcat_id = []
        for c in data['subcategory']:
            cat = (await session.execute(select(database.SubCategories).where(and_(database.SubCategories.name == c, database.SubCategories.category_id == cat_id)))).scalar_one_or_none()
            if cat is None:
                subcat_id.append((await session.execute(insert(database.SubCategories).values(name=c, category_id=cat_id))).inserted_primary_key[0])
            else:
                subcat_id.append(cat.id)
        data['category'] = cat_id
        data['subcategory'] = subcat_id
        await session.execute(insert(database.Tasks), data)
        await session.commit()
