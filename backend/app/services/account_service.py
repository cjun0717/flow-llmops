#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""账号设置服务。"""
from __future__ import annotations

import base64
import secrets

from datetime import datetime

import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import FailException
from app.models.account import Account
from app.utils.password import hash_password, validate_password

logger = logging.getLogger(__name__)


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
    async def seed_default_account(db: AsyncSession) -> Account | None:
        """启动时幂等创建默认账号。已存在则同步用户名和密码（便于改配置后重启生效）。"""
        email = (settings.DEFAULT_ACCOUNT_EMAIL or "").strip()
        password = settings.DEFAULT_ACCOUNT_PASSWORD or ""
        name = (settings.DEFAULT_ACCOUNT_NAME or "").strip() or (
            email.split("@", 1)[0] if email else ""
        )
        if not email or not password or not name:
            logger.info("未配置默认账号，跳过种子")
            return None

        validate_password(password)
        result = await db.execute(
            select(Account).where(or_(Account.email == email, Account.name == name))
        )
        account = result.scalars().first()
        if account is None:
            account = await AccountService.ensure_account(
                email=email, password=password, name=name, db=db
            )
            logger.info("已创建默认账号，用户名: %s", name)
            return account

        account.name = name
        account.email = email
        password_hashed, password_salt = AccountService._encode_password(password)
        account.password = password_hashed
        account.password_salt = password_salt
        await db.commit()
        await db.refresh(account)
        logger.info("已同步默认账号，用户名: %s", name)
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
        username = (name or "").strip()
        if username != account.name:
            result = await db.execute(
                select(Account.id).where(
                    Account.name == username,
                    Account.id != account.id,
                )
            )
            if result.scalar_one_or_none() is not None:
                raise FailException("用户名已存在")
        account.name = username
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
