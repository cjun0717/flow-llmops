#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置应用广场路由（迁移自 imooc builtin_app_handler.py）。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep, BuiltinAppManagerDep
from app.schemas.builtin_app import (
    AddBuiltinAppToSpaceData,
    AddBuiltinAppToSpaceReq,
    GetBuiltinAppCategoriesResp,
    GetBuiltinAppsResp,
)
from app.schemas.response import ApiResponse, ok
from app.services.builtin_app_service import BuiltinAppService

router = APIRouter(prefix="/builtin-apps", tags=["应用广场"])


@router.get("/categories", response_model=ApiResponse[list[GetBuiltinAppCategoriesResp]])
async def get_builtin_app_categories(
    _account: CurrentAccount,
    manager: BuiltinAppManagerDep,
) -> ApiResponse[list[GetBuiltinAppCategoriesResp]]:
    """获取内置应用分类列表"""
    categories = BuiltinAppService.get_categories(manager)
    return ok([GetBuiltinAppCategoriesResp.from_entity(item) for item in categories])


@router.get("", response_model=ApiResponse[list[GetBuiltinAppsResp]])
async def get_builtin_apps(
    _account: CurrentAccount,
    manager: BuiltinAppManagerDep,
) -> ApiResponse[list[GetBuiltinAppsResp]]:
    """获取所有内置应用列表"""
    builtin_apps = BuiltinAppService.get_builtin_apps(manager)
    return ok([GetBuiltinAppsResp.from_entity(item) for item in builtin_apps])


@router.post("/add-builtin-app-to-space", response_model=ApiResponse[AddBuiltinAppToSpaceData])
async def add_builtin_app_to_space(
    body: AddBuiltinAppToSpaceReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    manager: BuiltinAppManagerDep,
) -> ApiResponse[AddBuiltinAppToSpaceData]:
    """将指定的内置应用添加到个人空间"""
    app = await BuiltinAppService.add_builtin_app_to_space(
        body.builtin_app_id, account, db, manager
    )
    return ok(AddBuiltinAppToSpaceData(id=app.id))
