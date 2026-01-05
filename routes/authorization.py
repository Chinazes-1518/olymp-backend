import hashlib
from uuid import uuid4

from fastapi import APIRouter, HTTPException, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import select, insert, update
from pydantic import BaseModel, constr
from sqlalchemy.util import greenlet_spawn

import database
import secrets
import utils
router = APIRouter(prefix='/auth')

def hash_password(password: str) -> str:
    return hashlib.sha512((password + 'asejqweifqe39sasloQ!@').encode("utf-8")).hexdigest()


async def verify_token(session, token):
    item = await session.execute(select(database.Users).where(database.Users.token == token.strip()))
    if item.scalar_one_or_none() is None:
        raise HTTPException(403, {"error": "Токен недействителен"})



def generate_token() -> str:
    return secrets.token_hex(24)


class RegisterRestrictions(BaseModel):
    login: constr(min_length=4, max_length=30)
    password: constr(min_length=8, max_length=20)
    name: constr(min_length=1, max_length=50)
    surname: constr(min_length=1, max_length=50)
    role: constr(min_length=3, max_length=20)



@router.post('/register')
async def register(data: RegisterRestrictions) -> JSONResponse:
    async with database.sessions.begin() as session:
        request = await session.execute(select(database.Users).where(database.Users.login == data.login.strip()))
        user = request.scalar_one_or_none()
        if user is not None:
            raise HTTPException(418, {'error': 'Пользователь с таким логином уже существует'})
        token = generate_token()
        second_request = await session.execute(insert(database.Users).values(login=data.login.strip(),
                                                                             password_hash=hash_password(data.password.strip()),
                                                                             name=data.name,
                                                                             surname=data.surname,
                                                                             role=data.role,
                                                                             points=0,
                                                                             token=token))
        await session.commit()
        return utils.json_responce({'token': token,
                                    'id': second_request.inserted_primary_key[0]})



class LoginRestrictions(BaseModel):
    login: constr(min_length=4, max_length=30)
    password: constr(min_length=8, max_length=20)


@router.post('/login')
async def login(data: LoginRestrictions) -> JSONResponse:
    async with database.sessions.begin() as session:
          request = await session.execute(select(database.Users).where(database.Users.login == data.login.strip()))
          user = request.scalar_one_or_none()
          if user is None:
              raise HTTPException(403, {'error': 'Неверный логин или пароль'})
          if hash_password(data.password.strip()) != user.password:
              raise HTTPException(403, {'error': 'Неверный логин или пароль'})
          return utils.json_responce({'token': user.token, 'id': user.id, 'name':user.name, 'surname': user.surname})







