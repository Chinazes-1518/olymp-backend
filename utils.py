from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, insert, update
from gigachat import GigaChat
from sqlalchemy.ext import asyncio
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


def calculate_elo_rating(rating_a: int, rating_b: int, score_a: float, score_b: float, k_factor: int = 32) -> tuple[
    int, int]:
    E_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    E_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    rating_a_1 = rating_a + k_factor * (score_a - E_a)
    rating_b_1 = rating_b + k_factor * (score_b - E_b)
    return int(rating_a_1), int(rating_b_1)


def gigachat_check_answer(user_answer, task_condition, task_answer):
    with GigaChat(credentials=os.getenv('GIGACHAT_AUTHORIZATION_KEY'), verify_ssl_certs=False,
                  scope=os.getenv('GIGACHAT_API_PERS')) as giga:
        answer = giga.chat(json.dumps({'условие задачи': task_condition,
                                       'правильный ответ на задачу': task_answer,
                                       'ответ пользователя': user_answer,
                                       'формат ответа': 'Да или нет. Только одно слово без размышлений!!',
                                       'что нужно сделать':
                                           'проверить совпадает ли ответ пользователя с ответом автора на условие задачи, если ответ пользователя'
                                           'является синонимом к правильному ответ или ответ юзера верный но без уточнений, если это уточнение не влияет на правильность ответа, нужно засчитывать за правильный без объяснения'},
                                      ensure_ascii=False))
        return answer.choices[0].message.content


def gigachat_check_training_answer(user_answer, user_solution, task_condition, task_answer, task_solution):
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
                                           ' если не совпадает, проверить решение пользователя, если оно предоставлено, и объяснить где пользователь совершил ошибку, сравнивая с правильным решением задачи, правильное решение и правильный ответ и условие задачи нельзя подвергать сомнению! Если ответ пользователя неверный, то решение пользователя никак НЕ может быть верным и ты не должен с ним соглашаться, необходимо четко указать на ошибку в решении пользователя. в своём объяснении не используй markdown формат ответа, отвечай в виде html!!!'}, ensure_ascii=False))
        return answer.choices[0].message.content
