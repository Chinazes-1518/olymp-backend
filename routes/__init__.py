from fastapi import APIRouter
router = APIRouter()
from . import authorization
router.include_router(authorization.router)