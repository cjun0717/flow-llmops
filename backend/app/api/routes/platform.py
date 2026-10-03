#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第三方平台路由（迁移自 imooc platform_handler.py）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep
from app.schemas.platform import UpdateWechatConfigReq, WechatConfigData
from app.schemas.response import ApiResponse, ok
from app.services.platform_service import PlatformService

router = APIRouter(prefix="/platform", tags=["第三方平台"])


@router.get("/{app_id}/wechat-config", response_model=ApiResponse[WechatConfigData])
async def get_wechat_config(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[WechatConfigData]:
    """根据传递的 id 获取指定应用的微信配置"""
    data = await PlatformService.get_wechat_config(app_id, account, db)
    return ok(data)


@router.post("/{app_id}/wechat-config", response_model=ApiResponse[dict])
async def update_wechat_config(
    app_id: UUID,
    body: UpdateWechatConfigReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """根据传递的应用 id 更新该应用的微信发布配置"""
    await PlatformService.update_wechat_config(app_id, body, account, db)
    return ok({}, message="更新Agent应用微信公众号配置成功")
