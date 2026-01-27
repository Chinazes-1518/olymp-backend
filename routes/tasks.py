from re import sub
from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.params import Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select, and_, String, cast, Integer
from typing import Annotated, Optional, Union, List
import database
import utils
from sqlalchemy.dialects.postgresql import ARRAY
from fastapi.security import APIKeyHeader

API_Key_Header = APIKeyHeader(name='Authorization', auto_error=True)

router = APIRouter(prefix='/tasks')


@router.get('/get')
async def send_to_frontend(condition: Optional[str] = None,
                           level_start: Optional[int] = 0,
                           level_end: Optional[int] = 10,
                           category: Optional[int] = None,
                           subcategory: Optional[str] = None,
                           count: Optional[int] = 0) -> JSONResponse:
    async with database.sessions.begin() as session:
        tasks = select(database.Tasks)
        tasks = tasks.where(and_(
            database.Tasks.level >= level_start,
            database.Tasks.level <= level_end,
        ))
        if subcategory:
            subcategories = list(map(int, subcategory.strip().split(',')))
            tasks = tasks.where(cast(
                database.Tasks.subcategory,
                ARRAY(Integer)).op('&&')(subcategories))
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
            'solution': item.solution,
            'source': item.source,
            'answer_type': item.answer_type,
            'answer': item.answer
        } for item in tasks2]
        if condition and condition.isalpha():
            item = (await session.execute(select(database.Tasks).where(database.Tasks.id == int(condition)))).scalar_one_or_none()
            if item is not None:
                tasks_data.insert(0, {
                    'id': item.id,
                    'level': item.level,
                    'category': item.category,
                    'subcategory': item.subcategory,
                    'condition': item.condition,
                    'solution': item.solution,
                    'source': item.source,
                    'answer_type': item.answer_type,
                    'answer': item.answer
                })
        return utils.json_response({'tasks': tasks_data})


@router.get('/check_answer')
async def check_answer(answer: Annotated[str, Query],
                       id: Annotated[int, Query], token: str=Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {"error": "Токен не существует"})
        request = (await session.execute(select(database.Tasks).where(database.Tasks.id == id)))
        b = request.scalars().one_or_none()
        if b is None:
            raise HTTPException(403, {"error": "Задачи не существует"})
        get_answer = utils.gigachat_check_answer(answer, str(b.condition), str(b.answer))
        return utils.json_response({'Correct': get_answer.lower() == 'да'})



@router.get('/check_answer_and_solution')
async def check_answer_and_solution(answer: Annotated[str, Query], solution: Optional[str],
                       id: Annotated[int, Query], token: str=Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {"error": "Токен не существует"})
        request = (await session.execute(select(database.Tasks).where(database.Tasks.id == id)))
        b = request.scalars().one_or_none()
        if solution is None:
            get_answer = utils.gigachat_check_answer(answer, b.condition, b.answer)
            return utils.json_response({'Correct': get_answer.lower() == 'да'})
        get_answer = utils.gigachat_check_training_answer(answer, solution, b.condition, b.answer, b.solution)
        if get_answer.lower() == 'да':
            return utils.json_response({'correct': True})
        else:
            return utils.json_response({'correct': False, 'explanation': get_answer})



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


@router.get('/get_categories')
async def get_categories():
    async with database.sessions.begin() as session:
        request = (await session.execute(select(database.Categories)))
        b = request.scalars().all()
        categories_data = [{'id': item.id, 'name': item.name} for item in b]
        return utils.json_response({'categories': categories_data})


@router.get('/get_subcategories')
async def get_subcategories(category_id: Optional[int] = None):
    async with database.sessions.begin() as session:
        if category_id is None:
            request = await session.execute(select(database.SubCategories))
        else:
            request = await session.execute(select(database.SubCategories).where(database.SubCategories.category_id == category_id))
        b = request.scalars().all()
        subcategories_data = [{'id': item.id, 'name': item.name} for item in b]
        return utils.json_response({'subcategories': subcategories_data})
