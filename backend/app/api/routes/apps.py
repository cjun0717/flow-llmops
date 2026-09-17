#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用管理路由（CRUD）。"""
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep
from app.schemas.app import (
    AppDetailData,
    AppListItemData,
    CreateAppReq,
    CreateAppData,
    GetAppsWithPageReq,
    UpdateAppReq,
)
from app.schemas.response import ApiResponse, PageData, ok
from app.services.app_service import AppService

router = APIRouter(prefix="/apps", tags=["应用管理"])


@router.get("", response_model=ApiResponse[PageData[AppListItemData]])
async def get_apps_with_page(
    account: CurrentAccount,
    db: AsyncSessionDep,
    search_word: str = Query("", description="搜索词"),
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
) -> ApiResponse[PageData[AppListItemData]]:
    """获取当前登录账号的应用分页列表"""
    req = GetAppsWithPageReq(
        search_word=search_word,
        current_page=current_page,
        page_size=page_size,
    )
    data = await AppService.get_apps_with_page(req, account, db)
    return ok(data)


@router.post("", response_model=ApiResponse[CreateAppData])
async def create_app(
    body: CreateAppReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[CreateAppData]:
    """创建应用"""
    app = await AppService.create_app(body, account, db)
    return ok(CreateAppData(id=app.id))


@router.get("/{app_id}", response_model=ApiResponse[AppDetailData])
async def get_app(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[AppDetailData]:
    """获取应用详情"""
    data = await AppService.get_app_detail(app_id, account, db)
    return ok(data)


@router.post("/{app_id}", response_model=ApiResponse[dict])
async def update_app(
    app_id: UUID,
    body: UpdateAppReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """修改应用基础信息"""
    await AppService.update_app(app_id, body, account, db)
    return ok({}, message="修改Agent智能体应用成功")


@router.post("/{app_id}/delete", response_model=ApiResponse[dict])
async def delete_app(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """删除应用"""
    await AppService.delete_app(app_id, account, db)
    return ok({}, message="删除Agent智能体应用成功")


@router.post("/{app_id}/copy", response_model=ApiResponse[CreateAppData])
async def copy_app(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[CreateAppData]:
    """复制应用"""
    app = await AppService.copy_app(app_id, account, db)
    return ok(CreateAppData(id=app.id))
