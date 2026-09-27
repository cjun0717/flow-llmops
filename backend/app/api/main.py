from fastapi import APIRouter

from app.api.routes import (
    account,
    api_tools,
    apps,
    auth,
    builtin_tools,
    conversations,
    datasets,
    documents,
    language_models,
    mcp_tools,
    oauth,
    openapi,
    segments,
    upload_file,
    workflows,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(oauth.router)
api_router.include_router(account.router)
api_router.include_router(upload_file.router)
api_router.include_router(apps.router)
api_router.include_router(language_models.router)
api_router.include_router(datasets.router)
api_router.include_router(documents.router)
api_router.include_router(segments.router)
api_router.include_router(builtin_tools.router)
api_router.include_router(api_tools.router)
api_router.include_router(mcp_tools.router)
api_router.include_router(conversations.router)
api_router.include_router(workflows.router)
api_router.include_router(openapi.router)
