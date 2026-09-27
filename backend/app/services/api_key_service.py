#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""API 秘钥服务（async，迁移自 imooc api_key_service.py）。"""
from __future__ import annotations

import secrets
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ForbiddenException
from app.models.account import Account
from app.models.api_key import ApiKey
from app.schemas.api_key import (
    CreateApiKeyReq,
    GetApiKeysWithPageReq,
    GetApiKeysWithPageResp,
)
from app.schemas.response import PageData, page_data


class ApiKeyService:
    """API 秘钥服务"""

    @staticmethod
    async def create_api_key(req: CreateApiKeyReq, account: Account, db: AsyncSession) -> ApiKey:
        """根据传递的信息创建 API 秘钥"""
        api_key = ApiKey(
            account_id=account.id,
            api_key=ApiKeyService.generate_api_key(),
            is_active=req.is_active,
            remark=req.remark,
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        return api_key

    @staticmethod
    async def get_api_key(api_key_id: UUID, account: Account, db: AsyncSession) -> ApiKey:
        """根据秘钥id+账号信息获取记录并校验权限"""
        result = await db.execute(select(ApiKey).where(ApiKey.id == api_key_id))
        api_key = result.scalar_one_or_none()
        if not api_key or api_key.account_id != account.id:
            raise ForbiddenException("API秘钥不存在或无权限")
        return api_key

    @staticmethod
    async def get_api_key_by_credential(api_key: str, db: AsyncSession) -> ApiKey | None:
        """根据传递的凭证信息获取 ApiKey 记录"""
        result = await db.execute(select(ApiKey).where(ApiKey.api_key == api_key))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_api_key(
        api_key_id: UUID, account: Account, db: AsyncSession, **kwargs
    ) -> ApiKey:
        """根据传递的信息更新 API 秘钥"""
        api_key = await ApiKeyService.get_api_key(api_key_id, account, db)
        for key, value in kwargs.items():
            if hasattr(api_key, key):
                setattr(api_key, key, value)
        await db.commit()
        return api_key

    @staticmethod
    async def delete_api_key(api_key_id: UUID, account: Account, db: AsyncSession) -> ApiKey:
        """根据传递的id删除 API 秘钥"""
        api_key = await ApiKeyService.get_api_key(api_key_id, account, db)
        await db.delete(api_key)
        await db.commit()
        return api_key

    @staticmethod
    async def get_api_keys_with_page(
        req: GetApiKeysWithPageReq, account: Account, db: AsyncSession
    ) -> PageData[GetApiKeysWithPageResp]:
        """根据传递的信息获取 API 秘钥分页列表数据"""
        filters = [ApiKey.account_id == account.id]

        # 总数
        count_result = await db.execute(
            select(func.count()).select_from(ApiKey).where(*filters)
        )
        total_record = count_result.scalar() or 0

        # 分页数据
        result = await db.execute(
            select(ApiKey)
            .where(*filters)
            .order_by(desc(ApiKey.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        api_keys = result.scalars().all()

        items = [GetApiKeysWithPageResp.from_model(item) for item in api_keys]
        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @classmethod
    def generate_api_key(cls, api_key_prefix: str = "llmops-v1/") -> str:
        """生成一个长度为48的API秘钥，并携带前缀"""
        return api_key_prefix + secrets.token_urlsafe(48)
