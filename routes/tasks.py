from fastapi import APIRouter, HTTPException, FastAPI, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, insert, update, or_, and_, String, cast, func
from pydantic import BaseModel, constr
from sqlalchemy.util import greenlet_spawn
from typing import Annotated
import database
import utils
from .websocket import websocket_endpoint
from sqlalchemy.dialects.postgresql import ARRAY


router = APIRouter(prefix='/tasks')


@router.get('/get')
async def send_to_frontend(condition: Annotated[str, Query()],
                   level_start: Annotated[int, Query()],
                   level_end: Annotated[int, Query()],
                   category: Annotated[str, Query()],
                   subcategory: Annotated[list[str], Query()],
                   count: Annotated[int, Query()]) -> JSONResponse:
    async with database.sessions.begin() as session:
        tasks = (await session.execute(select(database.Tasks).where(
            and_(database.Tasks.condition.contains(condition),
                database.Tasks.level >= level_start,
                database.Tasks.level <= level_end,
                database.Tasks.category == category,
                cast(
                    database.Tasks.subcategory,
                    ARRAY(String)).op('&&')(
                    subcategory))).limit(count))).scalars().all()
        tasks_data = [{'id': item.id,
                       'level': item.level,
                       'category': item.category,
                       'subcategory': item.subcategory,
                       'condition': item.condition,
                       'source': item.source,
                       'answer_type': item.answer_type
                       } for item in tasks]
        return utils.json_response({'tasks': tasks_data})


@router.get('/check_answer')
async def check_answer(answer: Annotated[str, Query],
                       id: Annotated[int, Query]) -> JSONResponse:
    async with database.sessions.begin() as session:
        request = (await session.execute(select(database.Tasks)).where(database.Tasks.id == id))
        m = request.scalar_one_or_none()
        if m.answer == answer:
            return utils.json_response({'Correct': True})
        else:
            return utils.json_response({'Incorrect': False})

@router.get('/task_id')
async def find_task(id: Annotated[int, Query]):
    async with database.sessions.begin() as session:
        request = (await session.execute(select(database.Tasks)).where(database.Tasks.id == id))
        k = request.scalar_one_or_none()
        if k is None:
            raise HTTPException(403, {"error": "Задачи с таким id не существует"})
        else:
            return utils.json_response({'id': k.id, 'level': k.level, 'category': k.category,
                                        'subcategory': k.subcategory, 'condition': k.condition,
                                        'solution': k.solution, 'answer': k.answer, 'source': k.source,
                                        'answer_type': k.answer_type})

















