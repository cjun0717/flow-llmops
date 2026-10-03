#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用户模型目录路由。"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep
from app.schemas.response import ApiResponse, ok
from app.schemas.user_model import (
    CreateUserModelReq,
    ProbeUserModelReq,
    UpdateUserModelReq,
    UserModelItem,
)
from app.services.user_model_service import UserModelService

router = APIRouter(prefix="/user-models", tags=["用户模型"])


@router.get("", response_model=ApiResponse[list[UserModelItem]])
async def list_user_models(
    account: CurrentAccount,
    db: AsyncSessionDep,
    model_type: Optional[str] = Query(None, description="chat 或 embedding"),
) -> ApiResponse[list[UserModelItem]]:
    data = await UserModelService.list_models(account, db, model_type)
    return ok(data)


@router.post("", response_model=ApiResponse[UserModelItem])
async def create_user_model(
    body: CreateUserModelReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[UserModelItem]:
    record = await UserModelService.create_model(body, account, db)
    return ok(UserModelItem.from_model(record), message="添加模型成功")


@router.post("/probe", response_model=ApiResponse[dict])
async def probe_user_model(
    body: ProbeUserModelReq,
    _account: CurrentAccount,
) -> ApiResponse[dict]:
    models = await UserModelService.probe(body.base_url, body.api_key)
    return ok({"models": models})


@router.post("/{model_id}", response_model=ApiResponse[UserModelItem])
async def update_user_model(
    model_id: UUID,
    body: UpdateUserModelReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[UserModelItem]:
    record = await UserModelService.update_model(model_id, body, account, db)
    return ok(UserModelItem.from_model(record), message="更新模型成功")


@router.post("/{model_id}/default", response_model=ApiResponse[UserModelItem])
async def set_default_user_model(
    model_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[UserModelItem]:
    record = await UserModelService.set_default(model_id, account, db)
    return ok(UserModelItem.from_model(record), message="已设为默认模型")


@router.post("/{model_id}/delete", response_model=ApiResponse[dict])
async def delete_user_model(
    model_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    await UserModelService.delete_model(model_id, account, db)
    return ok({}, message="删除模型成功")
