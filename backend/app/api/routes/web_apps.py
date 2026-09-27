#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WebApp 路由（迁移自 imooc web_app_handler.py）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAccount
from app.deps import (
    AppConfigServiceDep,
    AsyncSessionDep,
    LanguageModelServiceDep,
    RetrievalServiceDep,
    SyncRedisDep,
)
from app.schemas.response import ApiResponse, ok
from app.schemas.web_app import (
    WebAppChatReq,
    WebAppConversationItem,
    WebAppInfoData,
)
from app.services.web_app_service import WebAppService

router = APIRouter(prefix="/web-apps", tags=["WebApp"])


@router.get("/{token}", response_model=ApiResponse[WebAppInfoData])
async def get_web_app(
    token: str,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
    language_model_service: LanguageModelServiceDep,
) -> ApiResponse[WebAppInfoData]:
    """根据传递的 token 凭证标识获取 WebApp 基础信息"""
    data = await WebAppService.get_web_app_info(
        token, db, app_config_service, language_model_service
    )
    return ok(data)


@router.post("/{token}/chat")
async def web_app_chat(
    token: str,
    body: WebAppChatReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
    language_model_service: LanguageModelServiceDep,
    retrieval_service: RetrievalServiceDep,
    sync_redis: SyncRedisDep,
) -> StreamingResponse:
    """根据传递的 token+query 与 WebApp 进行对话（SSE）"""
    generator = WebAppService.web_app_chat(
        token, body, account, db,
        app_config_service, language_model_service, retrieval_service, sync_redis,
    )
    return StreamingResponse(
        generator,
        status_code=200,
        media_type="text/event-stream",
    )


@router.post("/{token}/chat/{task_id}/stop", response_model=ApiResponse[dict])
async def stop_web_app_chat(
    token: str,
    task_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    sync_redis: SyncRedisDep,
) -> ApiResponse[dict]:
    """根据传递的 token+task_id 停止与 WebApp 的对话"""
    await WebAppService.stop_web_app_chat(token, task_id, account, db, sync_redis)
    return ok({}, message="停止WebApp会话成功")


@router.get("/{token}/conversations", response_model=ApiResponse[list[WebAppConversationItem]])
async def get_conversations(
    token: str,
    account: CurrentAccount,
    db: AsyncSessionDep,
    is_pinned: bool = Query(False, description="是否只返回置顶会话"),
) -> ApiResponse[list[WebAppConversationItem]]:
    """获取指定 WebApp 下当前账号的会话列表"""
    data = await WebAppService.get_conversations(token, is_pinned, account, db)
    return ok(data)
