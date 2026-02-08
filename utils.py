from __future__ import annotations

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, insert, update, and_, cast, Integer, func
from sqlalchemy.dialects.postgresql import ARRAY
from gigachat import GigaChat
from sqlalchemy.ext import asyncio as s_aio
import asyncio
from dotenv import load_dotenv
import json
import os
import database


def json_response(data: dict) -> JSONResponse:
    return JSONResponse(jsonable_encoder(data), headers={
        'Access-Control-Allow-Origin': '*'})


async def user_by_id(session, user_id: int):
    user = await session.execute(select(database.Users).where(database.Users.id == user_id))
    return user.scalar_one_or_none()


async def token_to_user(session, token: str) -> None:
    item = (
        await session.execute(select(database.Users).where(database.Users.token == token.strip()))).scalar_one_or_none()
    if item is None:
        return None
    else:
        return item


def level_to_points(level: int):
    return level * 10


def calculate_elo_rating(rating_a: int, rating_b: int, score_a: float, score_b: float, k_factor: int = 32) -> tuple[int, int]:
    E_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    E_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    rating_a_1 = rating_a + k_factor * (score_a - E_a)
    rating_b_1 = rating_b + k_factor * (score_b - E_b)
    return int(rating_a_1), int(rating_b_1)


def gigachat_check_answer_real(user_answer, task_condition, task_answer):
    with GigaChat(credentials=os.getenv('GIGACHAT_AUTHORIZATION_KEY'), verify_ssl_certs=False,
                  scope=os.getenv('GIGACHAT_API_PERS'), timeout=7) as giga:
        answer = giga.chat(json.dumps({'условие задачи': task_condition,
                                       'правильный ответ на задачу': task_answer,
                                       'ответ пользователя': user_answer,
                                       'формат ответа': 'Да или нет. Только одно слово без размышлений!!',
                                       'что нужно сделать':
                                           'проверить совпадает ли ответ пользователя с ответом автора на условие задачи, если ответ пользователя'
                                           'является синонимом к правильному ответ или ответ юзера верный но без уточнений, если это уточнение не влияет на правильность ответа, нужно засчитывать за правильный без объяснения.'
                                           'если в задаче несколько пунктов, совпадать должны все!'},
                                      ensure_ascii=False))
        return answer.choices[0].message.content


async def gigachat_check_answer(user_answer, task_condition, task_answer):
    return await asyncio.to_thread(
        gigachat_check_answer_real,
        user_answer, task_condition, task_answer
    )


def gigachat_check_training_answer_real(user_answer, user_solution, task_condition, task_answer, task_solution):
    with GigaChat(credentials=os.getenv('GIGACHAT_AUTHORIZATION_KEY'), verify_ssl_certs=False,
                  scope=os.getenv('GIGACHAT_API_PERS')) as giga:
        answer = giga.chat(json.dumps({'условие задачи': task_condition,
                                       'правильный ответ на задачу': task_answer,
                                       'правильное решение задачи': task_solution,
                                       'ответ пользователя': user_answer,
                                       'решение пользователя': user_solution,
                                       'что нужно сделать':
                                           'проверить совпадает ли ответ пользователя с правильным ответом на задачу, если он совпадает,'
                                           ' то вывести Да только одним словом ,'
                                           ' если не совпадает, проверить решение пользователя, если оно предоставлено, и объяснить где пользователь совершил ошибку, сравнивая с правильным решением задачи, правильное решение и правильный ответ и условие задачи нельзя подвергать сомнению! Если ответ пользователя неверный, то решение пользователя никак НЕ может быть верным и ты не должен с ним соглашаться, необходимо четко указать на ошибку в решении пользователя. в своём объяснении не используй markdown формат ответа, отвечай в виде html!!! правильный ответ нельзя напрямую говорить пользователю ни в коем случае!!! только указывать на его ошибку'}, ensure_ascii=False))
        return answer.choices[0].message.content


async def gigachat_check_training_answer(user_answer, user_solution, task_condition, task_answer, task_solution):
    return await asyncio.to_thread(
        gigachat_check_training_answer_real,
        user_answer, user_solution, task_condition, task_answer, task_solution
    )


async def filter_tasks(session: s_aio.AsyncSession, level_start: int, level_end: int, subcategory: str |
                       None, condition: str | None, category: int | None, random_tasks: bool, count: int, exclude: list[int] = []) -> list[dict]:
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
    if random_tasks:
        tasks = tasks.order_by(func.random())
    else:
        tasks = tasks.order_by(database.Tasks.id)
    if count is not None and count > 0:
        tasks = tasks.limit(count)
    if len(exclude) > 0:
        tasks = tasks.where(~database.Tasks.id.in_(exclude))

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
    if condition and condition.isnumeric() and int(condition):
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
    return tasks_data
