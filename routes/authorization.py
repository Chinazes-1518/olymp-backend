import hashlib
from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy import select, insert
from typing import Annotated
from fastapi.params import Depends

import database
import secrets
import utils

API_Key_Header = APIKeyHeader(name='Authorization', auto_error=True)

router = APIRouter(prefix='/auth')


def hash_password(password: str) -> str:
    return hashlib.sha512((password + 'asejqweifqe39sasloQ!@').encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_hex(24)


@router.post('/register')
async def register(login: Annotated[str, Query()],
                   password: Annotated[str, Query()],
                   name: Annotated[str, Query()],
                   surname: Annotated[str, Query()])-> JSONResponse:
    async with database.sessions.begin() as session:
        request = await session.execute(select(database.Users).where(database.Users.login == login.strip()))
        user = request.scalar_one_or_none()
        if user is not None:
            raise HTTPException(418, {'error': 'Пользователь с таким логином уже существует'})
        if not(1 <= len(name) <= 30):
            raise HTTPException(422, {'error': 'Длина имени должна быть от 1 до 30 символов'})
        if not(2 <= len(surname) <= 30):
            raise HTTPException(422, {'error': 'Длина имени должна быть от 2 до 30 символов'})
        if not(4 <= len(login) <= 20):
            raise HTTPException(422, {'error': 'Длина логина должна быть от 4 до 20 символов'})
        if not(6 <= len(password)):
            raise HTTPException(422, {'error': 'Длина пароля должна быть от 6 символов'})
        # if role == 'administrator':
        #     raise HTTPException(400, {'error': 'Роль администратора недоступна'})
        token = generate_token()
        second_request = await session.execute(insert(database.Users).values(login=login.strip(),
                                                                             password_hash=hash_password(password.strip()),
                                                                             name=name,
                                                                             surname=surname,
                                                                             role='user',
                                                                             points=1000,
                                                                             token=token))
        await session.commit()
        return utils.json_response({'token': token,
                                    'id': second_request.inserted_primary_key[0]})


@router.post('/login')
async def login(login: Annotated[str, Query()],
                   password: Annotated[str, Query()]) -> JSONResponse:
    async with database.sessions.begin() as session:
          request = await session.execute(select(database.Users).where(database.Users.login == login.strip()))
          user = request.scalar_one_or_none()
          if user is None:
              raise HTTPException(403, {'error': 'Неверный логин или пароль'})
          if len(login) < 4 or len(login) > 20:
              raise HTTPException(422, {'error': 'Длина логина должна быть от 4 до 30 символов'})
          if len(password) < 4:
              raise HTTPException(422, {'error': 'Длина пароля должна быть больше 3 символов'})
          if hash_password(password.strip()) != user.password_hash:
              raise HTTPException(403, {'error': 'Неверный логин или пароль'})
          if user.blocked:
              raise HTTPException(403, {
                  'error': 'Пользователь заблокирован!'
              })
          return utils.json_response({'token': user.token, 'id': user.id, 'name':user.name, 'surname': user.surname})


@router.get('/verify')
async def verify_token(token: str=Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {"error": "Токен не существует"})
        if user.blocked:
            raise HTTPException(403, {'error': 'Пользователь заблокирован!'})
        return utils.json_response({'token': user.token, 'id': user.id, 'name': user.name, 'surname': user.surname, 'status': user.status, 'training': user.current_training, 'login': user.login, 'points': user.points, 'role': user.role})


@router.post('/update')
async def update_user(
        name: Annotated[str, Query()],
        surname: Annotated[str, Query()],
        token: str = Depends(API_Key_Header)
) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if not (1 <= len(name) <= 30):
            raise HTTPException(422, {'error': 'Длина имени должна быть от 1 до 30 символов'})
        if not (2 <= len(surname) <= 30):
            raise HTTPException(422, {'error': 'Длина фамилии должна быть от 2 до 30 символов'})
        user.name = name.strip()
        user.surname = surname.strip()
        await session.commit()
        return utils.json_response({'success': True})