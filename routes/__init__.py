from fastapi import APIRouter
router = APIRouter()
from . import authorization
from . import administration
from . import websocket
from . import battle
from . import tasks
from . import analytics

router.include_router(authorization.router)
router.include_router(administration.router)
router.include_router(websocket.router)
router.include_router(battle.router)
router.include_router(tasks.router)
router.include_router(analytics.router)
