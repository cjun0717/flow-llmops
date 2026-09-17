#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""账号设置服务。"""
from __future__ import annotations

import base64
import secrets

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.utils.password import hash_password


class AccountService:
    """账号资料更新"""

    @staticmethod
    def _encode_password(password: str) -> tuple[str, str]:
        """明文密码 → (base64_hash, base64_salt)，对齐 imooc 存储格式。"""
        salt = secrets.token_bytes(16)
        base64_salt = base64.b64encode(salt).decode()
        password_hashed = hash_password(password, salt)
        base64_password_hashed = base64.b64encode(password_hashed).decode()
        return base64_password_hashed, base64_salt

    @staticmethod
    async def ensure_account(
        *,
        email: str,
        password: str,
        name: str = "测试账号",
        db: AsyncSession,
    ) -> Account:
        """按邮箱查找账号；不存在则创建（本地联调 / 测试用）。"""
        result = await db.execute(select(Account).where(Account.email == email))
        account = result.scalar_one_or_none()
        if account is not None:
            return account

        password_hashed, password_salt = AccountService._encode_password(password)
        account = Account(
            name=name,
            email=email,
            avatar="",
            password=password_hashed,
            password_salt=password_salt,
            last_login_at=datetime.now(),
            last_login_ip="",
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def update_password(
        *,
        account: Account,
        password: str,
        db: AsyncSession,
    ) -> None:
        password_hashed, password_salt = AccountService._encode_password(password)
        account.password = password_hashed
        account.password_salt = password_salt
        await db.commit()

    @staticmethod
    async def update_name(
        *,
        account: Account,
        name: str,
        db: AsyncSession,
    ) -> None:
        account.name = name
        await db.commit()

    @staticmethod
    async def update_avatar(
        *,
        account: Account,
        avatar: str,
        db: AsyncSession,
    ) -> None:
        account.avatar = avatar
        await db.commit()
