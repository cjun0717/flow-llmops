from fastapi import APIRouter

from app.api.routes import (
    account,
    apps,
    auth,
    language_models,
    oauth,
    upload_file,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(oauth.router)
api_router.include_router(account.router)
api_router.include_router(upload_file.router)
api_router.include_router(apps.router)
api_router.include_router(language_models.router)
