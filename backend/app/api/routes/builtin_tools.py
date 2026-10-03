#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置工具路由（4 端点）。"""
from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.deps import CurrentAccount
from app.deps import BuiltinToolServiceDep
from app.schemas.response import ApiResponse, ok

router = APIRouter(prefix="/builtin-tools", tags=["内置工具"])


@router.get("", response_model=ApiResponse[list])
async def get_builtin_tools(
    _account: CurrentAccount,
    service: BuiltinToolServiceDep,
) -> ApiResponse[list]:
    """获取 LLMOps 所有内置工具信息 + 提供商信息"""
    data = service.get_builtin_tools()
    return ok(data)


@router.get("/providers/{provider_name}/tools/{tool_name}", response_model=ApiResponse[dict])
async def get_provider_tool(
    provider_name: str,
    tool_name: str,
    _account: CurrentAccount,
    service: BuiltinToolServiceDep,
) -> ApiResponse[dict]:
    """根据传递的提供商名字 + 工具名字获取指定工具的信息"""
    data = service.get_provider_tool(provider_name, tool_name)
    return ok(data)


@router.get("/providers/{provider_name}/icon")
async def get_provider_icon(
    provider_name: str,
    service: BuiltinToolServiceDep,
) -> Response:
    """根据传递的提供商获取 icon 图标流信息（无需登录）"""
    icon, mimetype = service.get_provider_icon(provider_name)
    return Response(content=icon, media_type=mimetype)


@router.get("/categories", response_model=ApiResponse[list])
async def get_categories(
    _account: CurrentAccount,
    service: BuiltinToolServiceDep,
) -> ApiResponse[list]:
    """获取所有内置提供商的分类信息"""
    data = service.get_categories()
    return ok(data)


@router.get("/{provider_name}/icon")
async def get_provider_icon_alias(
    provider_name: str,
    service: BuiltinToolServiceDep,
) -> Response:
    """前端 img 使用 /builtin-tools/{name}/icon，与 providers 路径并存。"""
    icon, mimetype = service.get_provider_icon(provider_name)
    return Response(content=icon, media_type=mimetype)


@router.get("/{provider_name}/tools/{tool_name}", response_model=ApiResponse[dict])
async def get_provider_tool_alias(
    provider_name: str,
    tool_name: str,
    _account: CurrentAccount,
    service: BuiltinToolServiceDep,
) -> ApiResponse[dict]:
    """前端请求 /builtin-tools/{provider}/tools/{tool} 的兼容路径。"""
    data = service.get_provider_tool(provider_name, tool_name)
    return ok(data)
