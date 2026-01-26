from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select, update, insert, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import datetime, date, timedelta

import database
import utils

router = APIRouter(prefix='/analytics')



async def create_new_record(userid: int, session: AsyncSession):
    req = await session.execute(insert(database.Analytics).values(userid=userid, date=date.today(), data={'task_quantity': 0, 'answer_quantity': 0, 'time_per_task': {}}))
    return req.inserted_primary_key[0]


async def change_values(userid: int, count: dict):
    async with database.sessions.begin() as session:
        request = await session.execute(select(database.Users).where(database.Users.id == userid))
        b = request.scalar_one_or_none()
        if b is None:
            raise HTTPException(403, {'Error': 'Пользователя с таким id не существует'})
        req = await session.execute(select(database.Analytics).where(and_(database.Analytics.date == date.today(), userid == database.Analytics.userid)))
        row = req.scalar_one_or_none()
        if row is None:
            row_id = await create_new_record(userid, session)
            current = {'task_quantity': 0, 'answer_quantity': 0, 'time_per_task': {}}
        else:
            current = row.data
            row_id = row.id

        for k, v in count.items():
            if k in current:
                if k != 'time_per_task':
                     current[k] += v
                else:
                    current['time_per_task'] |= v
            else:
                if k != 'time_per_task':
                    current[k] = v
                else:
                    current['time_per_task'] |= v


        await session.execute(update(database.Analytics).where(database.Analytics.id == row_id).values(data=current))


@router.get('/get_userid_by_datetime')
async def get_userid_by_datetime(userid: int, start_date: datetime, final_date: datetime, token: Annotated[str, Header(alias="Authorization")]) -> JSONResponse:
            async with database.sessions.begin() as session:
                user = await utils.token_to_user(session, token)
                if user is None:
                    raise HTTPException(403, {'error': 'Пользователь не существует'})
                if user.role == 'administrator':
                    request = await session.execute(select(database.Analytics).where(start_date <= database.Analytics.date).where(
                            database.Analytics.date <= final_date).where(database.Analytics.id==userid))
                else:
                    request = await session.execute(
                        select(database.Analytics).where(start_date <= database.Analytics.date).where(
                            database.Analytics.date <= final_date).where(database.Analytics.id == user.id))
                return utils.json_response(request.scalars().all())
            







