from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import datetime, date, timedelta

import database
import utils

router = APIRouter(prefix='/analytics')





async def create_new_record(session: AsyncSession):
    req = await session.execute(insert(database.Analytics).values(date=date.today(), data={'task_quantity': 0, 'answer_quantity': 0, 'time_per_task': {}}))
    return req.inserted_primary_key[0]


async def change_values(count: dict, action: str):
    async with database.sessions.begin() as session:
        req = await session.execute(select(database.Analytics).where(database.Analytics.date == date.today()))
        row = req.scalar_one_or_none()
        if row is None:
            row_id = await create_new_record(session)
            current = {'task_quantity': 0, 'answer_quantity': 0, 'time_per_task': {}}
        else:
            current = row.data
            row_id = row.id  
        for k, v in count.items():
            if k in current[action]:
                current[action][k] += v
            else:
                current[action][k] = v

        await session.execute(update(database.Analytics).where(database.Analytics.id == row_id).values(data=current))