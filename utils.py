import hashlib
from uuid import uuid4
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException
from sqlalchemy import select

import database

<<<<<<< HEAD

def json_response(data: dict) -> JSONResponse:
    return JSONResponse(jsonable_encoder(data), headers={
                        'Access-Control-Allow-Origin': '*'})
=======
def json_response(data: dict) -> JSONResponse:
    return JSONResponse(jsonable_encoder(data), headers={'Access-Control-Allow-Origin': '*'})
>>>>>>> df9a7fecf6e294a3cdfb68debcc6e6e0d1ea4f3f


async def token_to_id(token: str) -> None | database.Users:
    async with database.sessions.begin() as session:
        item = (await session.execute(select(database.Users).where(database.Users.token == token.strip()))).scalar_one_or_none()
        if item is None:
            return None
        else:
            return item
