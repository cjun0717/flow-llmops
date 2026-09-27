#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""开放 API 路由（迁移自 imooc api_key_handler.py + openapi_handler.py）。

- /openapi/api-keys/*：API 秘钥管理（JWT 鉴权，CurrentAccount）
- /openapi/chat：开放 Chat 对话（ApiKey 鉴权，CurrentApiAccount）
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAccount, CurrentApiAccount
from app.deps import (
    AppConfigServiceDep,
    AsyncSessionDep,
    LanguageModelServiceDep,
    RetrievalServiceDep,
    SyncRedisDep,
)
from app.schemas.api_key import (
    CreateApiKeyReq,
    GetApiKeysWithPageResp,
    UpdateApiKeyIsActiveReq,
    UpdateApiKeyReq,
)
from app.schemas.openapi import OpenAPIChatReq
from app.schemas.response import ApiResponse, PageData, ok
from app.services.api_key_service import ApiKeyService
from app.services.app_service import AppService
from app.services.openapi_service import OpenAPIService

router = APIRouter(prefix="/openapi", tags=["开放API"])


# ===== API 秘钥管理（JWT 鉴权） =====


@router.get("/api-keys", response_model=ApiResponse[PageData[GetApiKeysWithPageResp]])
async def get_api_keys_with_page(
    account: CurrentAccount,
    db: AsyncSessionDep,
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
) -> ApiResponse[PageData[GetApiKeysWithPageResp]]:
    """获取当前登录账号的 API 秘钥分页列表"""
    from app.schemas.api_key import GetApiKeysWithPageReq
    req = GetApiKeysWithPageReq(current_page=current_page, page_size=page_size)
    data = await ApiKeyService.get_api_keys_with_page(req, account, db)
    return ok(data)


@router.post("/api-keys", response_model=ApiResponse[dict])
async def create_api_key(
    body: CreateApiKeyReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """创建 API 秘钥"""
    await ApiKeyService.create_api_key(body, account, db)
    return ok({}, message="创建API秘钥成功")


@router.post("/api-keys/{api_key_id}", response_model=ApiResponse[dict])
async def update_api_key(
    api_key_id: UUID,
    body: UpdateApiKeyReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """更新 API 秘钥"""
    await ApiKeyService.update_api_key(
        api_key_id, account, db, is_active=body.is_active, remark=body.remark
    )
    return ok({}, message="更新API秘钥成功")


@router.post("/api-keys/{api_key_id}/is-active", response_model=ApiResponse[dict])
async def update_api_key_is_active(
    api_key_id: UUID,
    body: UpdateApiKeyIsActiveReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """更新 API 秘钥激活状态"""
    await ApiKeyService.update_api_key(
        api_key_id, account, db, is_active=body.is_active
    )
    return ok({}, message="更新API秘钥激活状态成功")


@router.post("/api-keys/{api_key_id}/delete", response_model=ApiResponse[dict])
async def delete_api_key(
    api_key_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """删除 API 秘钥"""
    await ApiKeyService.delete_api_key(api_key_id, account, db)
    return ok({}, message="删除API秘钥成功")


# ===== 开放 Chat 对话（ApiKey 鉴权） =====


@router.post("/chat")
async def openapi_chat(
    body: OpenAPIChatReq,
    account: CurrentApiAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
    language_model_service: LanguageModelServiceDep,
    retrieval_service: RetrievalServiceDep,
    sync_redis: SyncRedisDep,
):
    """开放 Chat 对话接口，根据 stream 字段返回 SSE 流式或块内容"""
    if body.stream:
        generator = OpenAPIService.chat_stream(
            body, account, db, AppService, app_config_service,
            language_model_service, retrieval_service, sync_redis,
        )
        return StreamingResponse(
            generator,
            status_code=200,
            media_type="text/event-stream",
        )

    # 块内容输出
    data = await OpenAPIService.chat_block(
        body, account, db, AppService, app_config_service,
        language_model_service, retrieval_service, sync_redis,
    )
    return ok(data)
