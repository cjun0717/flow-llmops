#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MCP 工具路由（7 端点）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep, McpToolServiceDep
from app.schemas.mcp_tool import (
    CreateMcpToolReq,
    GetMcpToolProvidersWithPageReq,
    GetMcpToolProvidersWithPageResp,
    GetMcpToolProviderResp,
    GetMcpToolResp,
    UpdateMcpToolProviderReq,
    ValidateMcpSchemaReq,
)
from app.schemas.response import ApiResponse, PageData, ok

router = APIRouter(prefix="/mcp-tools", tags=["MCP工具"])


@router.get("", response_model=ApiResponse[PageData[GetMcpToolProvidersWithPageResp]])
async def get_mcp_tool_providers_with_page(
    _account: CurrentAccount,
    db: AsyncSessionDep,
    service: McpToolServiceDep,
    search_word: str = Query("", description="搜索词"),
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
) -> ApiResponse[PageData[GetMcpToolProvidersWithPageResp]]:
    """获取 MCP 工具提供者分页列表"""
    req = GetMcpToolProvidersWithPageReq(
        search_word=search_word,
        current_page=current_page,
        page_size=page_size,
    )
    data = await service.get_mcp_tool_providers_with_page(req, _account, db)
    return ok(data)


@router.post("/validate-mcp-schema", response_model=ApiResponse[list])
async def validate_mcp_schema(
    body: ValidateMcpSchemaReq,
    _account: CurrentAccount,
    service: McpToolServiceDep,
) -> ApiResponse[list]:
    """校验 MCP 配置并返回可用工具预览"""
    data = service.validate_mcp_schema(body.mcp_schema)
    return ok(data)


@router.post("", response_model=ApiResponse[dict])
async def create_mcp_tool_provider(
    body: CreateMcpToolReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: McpToolServiceDep,
) -> ApiResponse[dict]:
    """添加 MCP 服务器（支持批量）"""
    await service.create_mcp_tools(body, account, db)
    return ok({}, message="添加MCP服务器成功")


@router.post("/{provider_id}", response_model=ApiResponse[dict])
async def update_mcp_tool_provider(
    provider_id: UUID,
    body: UpdateMcpToolProviderReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: McpToolServiceDep,
) -> ApiResponse[dict]:
    """更新 MCP 服务器（仅单个）"""
    await service.update_mcp_tool_provider(provider_id, body, account, db)
    return ok({}, message="更新MCP服务器成功")


@router.get("/{provider_id}", response_model=ApiResponse[GetMcpToolProviderResp])
async def get_mcp_tool_provider(
    provider_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: McpToolServiceDep,
) -> ApiResponse[GetMcpToolProviderResp]:
    """根据 provider_id 获取 MCP 工具提供者"""
    data = await service.get_mcp_tool_provider(provider_id, account, db)
    return ok(data)


@router.get("/{provider_id}/tools/{tool_name}", response_model=ApiResponse[GetMcpToolResp])
async def get_mcp_tool(
    provider_id: UUID,
    tool_name: str,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: McpToolServiceDep,
) -> ApiResponse[GetMcpToolResp]:
    """根据 provider_id 和 tool_name 获取 MCP 工具详情"""
    data = await service.get_mcp_tool(provider_id, tool_name, account, db)
    return ok(data)


@router.post("/{provider_id}/delete", response_model=ApiResponse[dict])
async def delete_mcp_tool_provider(
    provider_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    service: McpToolServiceDep,
) -> ApiResponse[dict]:
    """删除 MCP 服务器"""
    await service.delete_mcp_tool_provider(provider_id, account, db)
    return ok({}, message="删除MCP服务器成功")
