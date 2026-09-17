#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""授权认证服务。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import FailException
from app.models.account import Account
from app.schemas.auth import PasswordLoginData
from app.utils.jwt import create_access_token
from app.utils.password import compare_password


class AuthService:
    """账号密码登录等认证逻辑"""

    @staticmethod
    async def password_login(
        *,
        email: str,
        password: str,
        client_ip: str,
        db: AsyncSession,
    ) -> PasswordLoginData:
        result = await db.execute(select(Account).where(Account.email == email))
        account = result.scalar_one_or_none()
        if not account:
            raise FailException("账号不存在或者密码错误，请核实后重试")

        if not account.is_password_set or not compare_password(
            password,
            account.password,
            account.password_salt,
        ):
            raise FailException("账号不存在或者密码错误，请核实后重试")

        expire_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire_at = int((datetime.now(timezone.utc) + expire_delta).timestamp())
        access_token = create_access_token(account.id, expires_delta=expire_delta)

        account.last_login_at = datetime.now()
        account.last_login_ip = client_ip or ""
        await db.commit()
        await db.refresh(account)

        return PasswordLoginData(access_token=access_token, expire_at=expire_at)
