from fastapi import APIRouter

from api.v1 import (
    auth,
    account,
    upload_file
)
from .deps import CurrentUser
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(account.router)
api_router.include_router(upload_file.router,dependencies=[CurrentUser])
