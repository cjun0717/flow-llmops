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
from app.exceptions import UnauthorizedError
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
        raise UnauthorizedError("该接口需要授权才能访问，请登录后尝试")

    payload = parse_access_token(credentials.credentials)
    account_id = payload.get("sub")
    if not account_id:
        raise UnauthorizedError("解析token出错，请重新登陆")

    try:
        account_uuid = uuid.UUID(str(account_id))
    except ValueError as e:
        raise UnauthorizedError("解析token出错，请重新登陆") from e

    result = await db.execute(select(Account).where(Account.id == account_uuid))
    account = result.scalar_one_or_none()
    if account is None:
        raise UnauthorizedError("当前账户不存在，请重新登录")
    return account
