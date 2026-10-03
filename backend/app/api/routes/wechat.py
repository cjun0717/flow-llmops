#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""微信公众号回调路由（迁移自 imooc wechat_handler.py）。无需 JWT。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.deps import (
    AppConfigServiceDep,
    AsyncSessionDep,
    LanguageModelServiceDep,
    RetrievalServiceDep,
    SyncRedisDep,
)
from app.services.wechat_service import WechatService

router = APIRouter(prefix="/wechat", tags=["微信公众号"])


@router.api_route("/{app_id}", methods=["GET", "POST"])
async def wechat(
    app_id: UUID,
    request: Request,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
    language_model_service: LanguageModelServiceDep,
    retrieval_service: RetrievalServiceDep,
    sync_redis: SyncRedisDep,
) -> Response:
    """Agent 微信 API 校验与消息推送"""
    return await WechatService.handle(
        app_id,
        request,
        db,
        app_config_service,
        language_model_service,
        retrieval_service,
        sync_redis,
    )
