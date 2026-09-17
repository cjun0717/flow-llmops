#!/usr/bin/env python
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep
from app.schemas.account import (
    AccountInfoData,
    UpdateAvatarReq,
    UpdateNameReq,
    UpdatePasswordReq,
)
from app.schemas.response import ApiResponse, ok
from app.services.account_service import AccountService

router = APIRouter(prefix="/account", tags=["账号设置"])


@router.get("", response_model=ApiResponse[AccountInfoData])
async def get_current_user(
    account: CurrentAccount,
) -> ApiResponse[AccountInfoData]:
    """获取当前登录账号信息"""
    return ok(AccountInfoData.from_model(account))


@router.post("/password", response_model=ApiResponse[dict])
async def update_password(
    body: UpdatePasswordReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """修改当前登录账号密码"""
    await AccountService.update_password(
        account=account,
        password=body.password,
        db=db,
    )
    return ok({}, message="修改当前登录账号密码成功")


@router.post("/name", response_model=ApiResponse[dict])
async def update_name(
    body: UpdateNameReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """修改当前登录账号名称"""
    await AccountService.update_name(account=account, name=body.name, db=db)
    return ok({}, message="修改账号名称成功")


@router.post("/avatar", response_model=ApiResponse[dict])
async def update_avatar(
    body: UpdateAvatarReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """修改当前登录账号头像"""
    await AccountService.update_avatar(
        account=account,
        avatar=str(body.avatar),
        db=db,
    )
    return ok({}, message="修改账号头像成功")
