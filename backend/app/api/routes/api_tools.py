#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""自定义 API 工具路由（7 端点）。

注意：静态路径 validate-openapi-schema 必须注册在动态路径 /{provider_id} 之前，
否则会被 /{provider_id} 抢先匹配（UUID 解析失败）。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount
from app.deps import ApiToolServiceDep, AsyncSessionDep
from app.schemas.api_tool import (
    CreateApiToolReq,
    GetApiToolProvidersWithPageReq,
    GetApiToolProvidersWithPageResp,
    GetApiToolProviderResp,
    GetApiToolResp,
    UpdateApiToolProviderReq,
)
from app.schemas.response import ApiResponse, PageData, ok

router = APIRouter(prefix="/api-tools", tags=["API工具"])


@router.get("", response_model=ApiResponse[PageData[GetApiToolProvidersWithPageResp]])
async def get_api_tool_providers_with_page(
    _account: CurrentAccount,
    db: AsyncSessionDep,
    service: ApiToolServiceDep,
    search_word: str = Query("", description="搜索词"),
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
) -> ApiResponse[PageData[GetApiToolProvidersWithPageResp]]:
    """获取 API 工具提供者列表信息，该接口支持分页"""
    req = GetApiToolProvidersWithPageReq(
        search_word=search_word,
        current_page=current_page,
        page_size=page_size,
    )
    data = await service.get_api_tool_providers_with_page(req, _account, db)
    return ok(data)


@router.post("/validate-openapi-schema", response_model=ApiResponse[dict])
async def validate_openapi_schema(
    body: CreateApiToolReq,
    _account: CurrentAccount,
    service: ApiToolServiceDep,
) -> ApiResponse[dict]:
    """校验传递的 openapi_schema 字符串是否正确"""
    service.parse_openapi_schema(body.openapi_schema)
    return ok({}, message="数据校验成功")


@router.post("", response_model=ApiResponse[dict])
async def create_api_tool_provider(
    body: CreateApiToolReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: ApiToolServiceDep,
) -> ApiResponse[dict]:
    """创建自定义 API 工具"""
    await service.create_api_tool(body, account, db)
    return ok({}, message="创建自定义API插件成功")


@router.post("/{provider_id}/delete", response_model=ApiResponse[dict])
async def delete_api_tool_provider(
    provider_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: ApiToolServiceDep,
) -> ApiResponse[dict]:
    """根据传递的 provider_id 删除对应的工具提供者信息"""
    await service.delete_api_tool_provider(provider_id, account, db)
    return ok({}, message="删除自定义API插件成功")


@router.post("/{provider_id}", response_model=ApiResponse[dict])
async def update_api_tool_provider(
    provider_id: UUID,
    body: UpdateApiToolProviderReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: ApiToolServiceDep,
) -> ApiResponse[dict]:
    """更新自定义 API 工具提供者信息"""
    await service.update_api_tool_provider(provider_id, body, account, db)
    return ok({}, message="更新自定义API插件成功")


@router.get("/{provider_id}/tools/{tool_name}", response_model=ApiResponse[GetApiToolResp])
async def get_api_tool(
    provider_id: UUID,
    tool_name: str,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: ApiToolServiceDep,
) -> ApiResponse[GetApiToolResp]:
    """根据传递的 provider_id + tool_name 获取工具的详情信息"""
    data = await service.get_api_tool(provider_id, tool_name, account, db)
    return ok(data)


@router.get("/{provider_id}", response_model=ApiResponse[GetApiToolProviderResp])
async def get_api_tool_provider(
    provider_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: ApiToolServiceDep,
) -> ApiResponse[GetApiToolProviderResp]:
    """根据传递的 provider_id 获取工具提供者的原始信息"""
    data = await service.get_api_tool_provider(provider_id, account, db)
    return ok(data)
