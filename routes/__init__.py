from fastapi import APIRouter
router = APIRouter()
from . import authorization
from . import administration


router.include_router(authorization.router)
router.include_router(administration.router)