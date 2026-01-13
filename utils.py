import hashlib
from uuid import uuid4
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException
from sqlalchemy import select

import database


def json_response(data: dict) -> JSONResponse:
    return JSONResponse(jsonable_encoder(data), headers={
                        'Access-Control-Allow-Origin': '*'})


async def token_to_id(token: str) -> None | database.Users:
    async with database.sessions.begin() as session:
        item = (await session.execute(select(database.Users).where(database.Users.token == token.strip()))).scalar_one_or_none()
        if item is None:
            return None
        else:
            return item
