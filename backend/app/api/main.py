from fastapi import APIRouter

from app.api.routes import (
    account,
    ai,
    analysis,
    api_tools,
    apps,
    assistant_agent,
    audio,
    auth,
    builtin_tools,
    conversations,
    datasets,
    documents,
    mcp_tools,
    oauth,
    openapi,
    segments,
    upload_file,
    user_models,
    workflows,
    builtin_apps,
    web_apps,
    platform,
    wechat,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(oauth.router)
api_router.include_router(account.router)
api_router.include_router(upload_file.router)
api_router.include_router(apps.router)
api_router.include_router(user_models.router)
api_router.include_router(datasets.router)
api_router.include_router(documents.router)
api_router.include_router(segments.router)
api_router.include_router(builtin_tools.router)
api_router.include_router(api_tools.router)
api_router.include_router(mcp_tools.router)
api_router.include_router(conversations.router)
api_router.include_router(workflows.router)
api_router.include_router(openapi.router)
api_router.include_router(ai.router)
api_router.include_router(builtin_apps.router)
api_router.include_router(assistant_agent.router)
api_router.include_router(analysis.router)
api_router.include_router(web_apps.router)
api_router.include_router(audio.router)
api_router.include_router(platform.router)
api_router.include_router(wechat.router)
