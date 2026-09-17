#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""语言模型路由（只读）。"""
from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.deps import CurrentAccount
from app.deps import LanguageModelServiceDep
from app.schemas.response import ApiResponse, ok

router = APIRouter(prefix="/language-models", tags=["语言模型"])


@router.get("", response_model=ApiResponse[list])
async def get_language_models(
    account: CurrentAccount,
    svc: LanguageModelServiceDep,
) -> ApiResponse[list]:
    """获取所有语言模型提供商列表"""
    data = svc.get_language_models()
    return ok(data)


@router.get("/{provider_name}/icon")
async def get_language_model_icon(
    provider_name: str,
    svc: LanguageModelServiceDep,
) -> Response:
    """获取指定提供商的图标（原始 imooc 未加 @login_required，保持公开）"""
    icon, mimetype = svc.get_language_model_icon(provider_name)
    return Response(content=icon, media_type=mimetype)


@router.get("/{provider_name}/{model_name}", response_model=ApiResponse[dict])
async def get_language_model(
    provider_name: str,
    model_name: str,
    account: CurrentAccount,
    svc: LanguageModelServiceDep,
) -> ApiResponse[dict]:
    """获取指定模型的详细信息"""
    data = svc.get_language_model(provider_name, model_name)
    return ok(data)
