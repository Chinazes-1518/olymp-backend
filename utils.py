
import hashlib
from uuid import uuid4
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException
from sqlalchemy import select

import database

def json_responce(data: dict) -> JSONResponse:
    return JSONResponse(jsonable_encoder(data), headers={'Access-Control-Allow-Origin': '*'})


