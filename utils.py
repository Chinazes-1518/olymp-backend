import hashlib
from uuid import uuid4
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException
from sqlalchemy import select

import database
from database.database import Users


def json_response(data: dict) -> JSONResponse:
    return JSONResponse(jsonable_encoder(data), headers={
                        'Access-Control-Allow-Origin': '*'})


async def token_to_user(session, token: str) -> None:
    item = (await session.execute(select(database.Users).where(database.Users.token == token.strip()))).scalar_one_or_none()
    if item is None:
        return None
    else:
        return item

async def user_by_id(session, id: int) -> Users | None:
    return (await session.execute(select(Users).where(Users.id == id))).scalar_one_or_none()