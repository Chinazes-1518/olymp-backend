from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.params import Depends
from fastapi.responses import JSONResponse
from sqlalchemy import update
import database
import utils
from fastapi.security import APIKeyHeader
from typing import Annotated, Optional
import base64
import json

API_Key_Header = APIKeyHeader(name='Authorization', auto_error=True)

router = APIRouter(prefix='/status')


@router.get('/status_training_begin')
async def get_status_training_begin(token: str = Depends(API_Key_Header)):
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': "Пользователь не найден"})
        user.status = 'training'
        await session.commit()


@router.get('/status_training_end')
async def get_status_training_end(token: str = Depends(API_Key_Header)):
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': "Пользователь не найден"})
        user.status = None
        await session.commit()


@router.get('/get_status')
async def get_status(token: str = Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': "Пользователь не найден"})
        return utils.json_response({'status': user.status})


@router.get('/get_training')
async def get_training(token: str = Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': "Пользователь не найден"})
        return utils.json_response({'training': user.current_training})


@router.get('/set_training')
async def set_training(training: Annotated[str, Query()], token: str = Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': "Пользователь не найден"})
        await session.execute(update(database.Users).where(database.Users.id == user.id).values(current_training = json.loads(base64.b64decode(training)) if training != 'null' else None))

