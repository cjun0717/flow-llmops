#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""API 层依赖：鉴权等。"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.exceptions import UnauthorizedException
from app.models.account import Account
from app.utils.jwt import parse_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_account(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Account:
    """
    解析 Authorization: Bearer <access_token>，返回当前登录账号。
    对齐 imooc：JWT payload.sub = account_id。
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedException("该接口需要授权才能访问，请登录后尝试")

    payload = parse_access_token(credentials.credentials)
    account_id = payload.get("sub")
    if not account_id:
        raise UnauthorizedException("解析token出错，请重新登陆")

    try:
        account_uuid = uuid.UUID(str(account_id))
    except ValueError as e:
        raise UnauthorizedException("解析token出错，请重新登陆") from e

    result = await db.execute(select(Account).where(Account.id == account_uuid))
    account = result.scalar_one_or_none()
    if account is None:
        raise UnauthorizedException("当前账户不存在，请重新登录")
    return account


CurrentAccount = Annotated[Account, Depends(get_current_account)]


async def get_current_api_account(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Account:
    """
    解析 Authorization: Bearer <api_key>，根据 ApiKey 凭证返回归属账号。
    对齐 imooc openapi 蓝图：使用 ApiKey 鉴权（非 JWT）。
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedException("该接口需要授权才能访问，请登录后尝试")

    api_key = credentials.credentials
    from app.services.api_key_service import ApiKeyService

    api_key_record = await ApiKeyService.get_api_key_by_credential(api_key, db)
    if not api_key_record or not api_key_record.is_active:
        raise UnauthorizedException("该秘钥不存在或未激活")

    result = await db.execute(select(Account).where(Account.id == api_key_record.account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise UnauthorizedException("当前账户不存在，请重新登录")
    return account


CurrentApiAccount = Annotated[Account, Depends(get_current_api_account)]
