#!/usr/bin/env python
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep
from app.schemas.auth import PasswordLoginData, PasswordLoginReq
from app.schemas.response import ApiResponse, ok
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["授权认证"])


@router.post("/password-login", response_model=ApiResponse[PasswordLoginData])
async def password_login(
    body: PasswordLoginReq,
    request: Request,
    db: AsyncSessionDep,
) -> ApiResponse[PasswordLoginData]:
    """账号密码登录"""
    client_ip = request.client.host if request.client else ""
    data = await AuthService.password_login(
        email=str(body.email),
        password=body.password,
        client_ip=client_ip,
        db=db,
    )
    return ok(data)


@router.post("/logout", response_model=ApiResponse[dict])
async def logout(
    _account: CurrentAccount,
) -> ApiResponse[dict]:
    """退出登录（前端清 token；后端可后续加黑名单）"""
    return ok({}, message="退出当前账号成功")
