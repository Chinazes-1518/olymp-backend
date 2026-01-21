from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, and_, String, cast
from typing import Annotated, Optional
import database
import utils
from sqlalchemy.dialects.postgresql import ARRAY


router = APIRouter(prefix='/tasks')


@router.get('/get')
async def send_to_frontend(condition: Optional[str] = None,
                           level_start: Optional[int] = 0,
                           level_end: Optional[int] = 10,
                           category: Optional[str] = None,
                           subcategory: Optional[list[str]] = [],
                           count: Optional[int] = 0) -> JSONResponse:
    async with database.sessions.begin() as session:
        tasks = select(database.Tasks)
        tasks = tasks.where(and_(
            database.Tasks.level >= level_start,
            database.Tasks.level <= level_end,
        ))
        if subcategory:
            tasks = tasks.where(cast(
                database.Tasks.subcategory,
                ARRAY(String)).op('&&')(subcategory))
        if condition is not None:
            tasks = tasks.where(database.Tasks.condition.icontains(condition))
        if category is not None:
            tasks = tasks.where(database.Tasks.category == category)
        if count is not None and count > 0:
            tasks = tasks.limit(count)

        tasks2 = (await session.execute(tasks)).scalars().all()
        tasks_data = [{
            'id': item.id,
            'level': item.level,
            'category': item.category,
            'subcategory': item.subcategory,
            'condition': item.condition,
            'source': item.source,
            'answer_type': item.answer_type,
            'answer': item.answer
        } for item in tasks2]
        return utils.json_response({'tasks': tasks_data})


@router.get('/check_answer')
async def check_answer(answer: Annotated[str, Query],
                       id: Annotated[int, Query]) -> JSONResponse:
    async with database.sessions.begin() as session:
        request = (await session.execute(select(database.Tasks).where(database.Tasks.id == id)))
        m = request.scalar_one_or_none()
        if m.answer == answer:
            return utils.json_response({'Correct': True})
        else:
            return utils.json_response({'Incorrect': False})


@router.get('/task_id')
async def find_task(id: Annotated[int, Query]):
    async with database.sessions.begin() as session:
        request = (await session.execute(select(database.Tasks).where(database.Tasks.id == id)))
        k = request.scalar_one_or_none()
        if k is None:
            raise HTTPException(
                403, {"error": "Задачи с таким id не существует"})
        else:
            return utils.json_response({'id': k.id, 'level': k.level, 'category': k.category,
                                        'subcategory': k.subcategory, 'condition': k.condition,
                                        'solution': k.solution, 'answer': k.answer, 'source': k.source,
                                        'answer_type': k.answer_type})
