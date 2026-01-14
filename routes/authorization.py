import hashlib
from uuid import uuid4

from fastapi import APIRouter, HTTPException, FastAPI, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, insert, update
from pydantic import BaseModel, constr
from sqlalchemy.util import greenlet_spawn
from typing import Annotated

import database
import secrets
import utils
router = APIRouter(prefix='/auth')

def hash_password(password: str) -> str:
    return hashlib.sha512((password + 'asejqweifqe39sasloQ!@').encode("utf-8")).hexdigest()





def generate_token() -> str:
    return secrets.token_hex(24)



@router.post('/register')
async def register(login: Annotated[str, Query(max_length=30, min_length=4)],
                   password: Annotated[str, Query(max_length=20, min_length=4)],
                   name: Annotated[str, Query(max_length=50, min_length=1)],
                   surname: Annotated[str, Query(max_length=50, min_length=1)],
                   role: Annotated[str, Query(max_length=50, min_length=1)])-> JSONResponse:
    async with database.sessions.begin() as session:
        request = await session.execute(select(database.Users).where(database.Users.login == login.strip()))
        user = request.scalar_one_or_none()
        if user is not None:
            raise HTTPException(418, {'error': 'Пользователь с таким логином уже существует'})
        if role == 'administrator':
            raise HTTPException(400, {'error': 'Роль администратора недоступна'})
        token = generate_token()
        second_request = await session.execute(insert(database.Users).values(login=login.strip(),
                                                                             password_hash=hash_password(password.strip()),
                                                                             name=name,
                                                                             surname=surname,
                                                                             role=role,
                                                                             points=0,
                                                                             token=token))
        await session.commit()
        return utils.json_response({'token': token,
                                    'id': second_request.inserted_primary_key[0]})



class LoginRestrictions(BaseModel):
    login: constr(min_length=4, max_length=30)
    password: constr(min_length=8, max_length=20)


@router.post('/login')
async def login(login: Annotated[str, Query(max_length=30, min_length=4)],
                   password: Annotated[str, Query(max_length=20, min_length=4)]) -> JSONResponse:
    async with database.sessions.begin() as session:
          request = await session.execute(select(database.Users).where(database.Users.login == login.strip()))
          user = request.scalar_one_or_none()
          if user is None:
              raise HTTPException(403, {'error': 'Неверный логин или пароль'})
          if hash_password(password.strip()) != user.password_hash:
              raise HTTPException(403, {'error': 'Неверный логин или пароль'})
          return utils.json_response({'token': user.token, 'id': user.id, 'name':user.name, 'surname': user.surname})





router.post('/verify')
async def verify_token(token: str) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {"error": "Токен не существует"})
        return utils.json_response({'token': user.token, 'id': user.id, 'name': user.name, 'surname': user.surname})







