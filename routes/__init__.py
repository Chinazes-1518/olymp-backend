from fastapi import APIRouter
router = APIRouter()
from . import authorization
from . import administration
from . import websocket


router.include_router(authorization.router)
router.include_router(administration.router)
router.include_router(websocket.router)