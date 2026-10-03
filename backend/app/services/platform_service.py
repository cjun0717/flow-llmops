#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第三方平台服务（async，迁移自 imooc platform_service.py + App.wechat_config）。"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.entities.app_entity import AppStatus
from app.entities.platform_entity import WechatConfigStatus
from app.lib.helper import datetime_to_timestamp
from app.models.account import Account
from app.models.app import App
from app.models.platform import WechatConfig
from app.schemas.platform import UpdateWechatConfigReq, WechatConfigData
from app.services.app_service import AppService


class PlatformService:
    """微信公众号发布配置"""

    @staticmethod
    def compute_wechat_status(
        app_status: str,
        wechat_app_id: str | None,
        wechat_app_secret: str | None,
        wechat_token: str | None,
    ) -> WechatConfigStatus:
        """三个凭证齐全且应用已发布才视为已配置。"""
        filled = bool(wechat_app_id and wechat_app_secret and wechat_token)
        if app_status == AppStatus.DRAFT or not filled:
            return WechatConfigStatus.UNCONFIGURED
        return WechatConfigStatus.CONFIGURED

    @staticmethod
    def to_wechat_config_data(config: WechatConfig) -> WechatConfigData:
        prefix = (settings.SERVICE_API_PREFIX or "").rstrip("/")
        return WechatConfigData(
            app_id=config.app_id,
            url=f"{prefix}/wechat/{config.app_id}",
            ip=settings.SERVICE_IP or "",
            wechat_app_id=config.wechat_app_id or "",
            wechat_app_secret=config.wechat_app_secret or "",
            wechat_token=config.wechat_token or "",
            status=config.status or WechatConfigStatus.UNCONFIGURED,
            updated_at=datetime_to_timestamp(config.updated_at),
            created_at=datetime_to_timestamp(config.created_at),
        )

    @staticmethod
    async def get_or_create_wechat_config(app: App, db: AsyncSession) -> WechatConfig:
        """获取应用微信配置，不存在则创建；并按发布状态校正 status。"""
        result = await db.execute(select(WechatConfig).where(WechatConfig.app_id == app.id))
        config = result.scalar_one_or_none()
        if not config:
            config = WechatConfig(
                app_id=app.id,
                status=WechatConfigStatus.UNCONFIGURED,
            )
            db.add(config)
            await db.flush()

        new_status = PlatformService.compute_wechat_status(
            app.status, config.wechat_app_id, config.wechat_app_secret, config.wechat_token
        )
        if config.status != new_status:
            config.status = new_status
        await db.commit()
        await db.refresh(config)
        return config

    @staticmethod
    async def get_wechat_config(
        app_id: UUID, account: Account, db: AsyncSession
    ) -> WechatConfigData:
        """根据应用 id 获取微信发布配置"""
        app = await AppService.get_app(app_id, account, db)
        config = await PlatformService.get_or_create_wechat_config(app, db)
        return PlatformService.to_wechat_config_data(config)

    @staticmethod
    async def update_wechat_config(
        app_id: UUID, req: UpdateWechatConfigReq, account: Account, db: AsyncSession
    ) -> WechatConfig:
        """更新应用的微信发布配置"""
        app = await AppService.get_app(app_id, account, db)
        config = await PlatformService.get_or_create_wechat_config(app, db)
        config.wechat_app_id = req.wechat_app_id or ""
        config.wechat_app_secret = req.wechat_app_secret or ""
        config.wechat_token = req.wechat_token or ""
        config.status = PlatformService.compute_wechat_status(
            app.status, config.wechat_app_id, config.wechat_app_secret, config.wechat_token
        )
        await db.commit()
        await db.refresh(config)
        return config
