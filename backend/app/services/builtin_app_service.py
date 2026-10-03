#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置应用广场服务（async，迁移自 imooc builtin_app_service.py）。"""
from __future__ import annotations

import mimetypes
import os
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.builtin_apps import BuiltinAppManager
from app.core.builtin_apps.entities.builtin_app_entity import BuiltinAppEntity
from app.core.builtin_apps.entities.category_entity import CategoryEntity
from app.entities.app_entity import AppConfigType, AppStatus
from app.exceptions import NotFoundException
from app.models.account import Account
from app.models.app import App, AppConfigVersion


class BuiltinAppService:
    """内置应用服务"""

    @staticmethod
    def builtin_app_icon_url(builtin_app_id: str) -> str:
        """浏览器可访问的内置应用图标地址。"""
        return f"{settings.SERVICE_API_PREFIX.rstrip('/')}/builtin-apps/{builtin_app_id}/icon"

    @staticmethod
    def get_categories(manager: BuiltinAppManager) -> list[CategoryEntity]:
        """获取分类列表信息"""
        return manager.get_categories()

    @staticmethod
    def get_builtin_apps(manager: BuiltinAppManager) -> list[BuiltinAppEntity]:
        """获取所有内置应用实体信息列表"""
        return manager.get_builtin_apps()

    @staticmethod
    def get_builtin_app_icon(manager: BuiltinAppManager, builtin_app_id: str) -> tuple[bytes, str]:
        """读取内置应用本地图标。"""
        builtin_app = manager.get_builtin_app(builtin_app_id)
        if not builtin_app:
            raise NotFoundException("该内置应用不存在，请核实后重试")

        filename = builtin_app.icon
        if filename.startswith("http"):
            filename = f"{builtin_app_id}.svg"
        icons_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "core",
            "builtin_apps",
            "icons",
        )
        icon_path = os.path.normpath(os.path.join(icons_dir, filename))
        if not os.path.isfile(icon_path):
            raise NotFoundException("该内置应用未提供图标")

        mimetype, _ = mimetypes.guess_type(icon_path)
        with open(icon_path, "rb") as f:
            return f.read(), mimetype or "image/svg+xml"

    @staticmethod
    async def add_builtin_app_to_space(
        builtin_app_id: UUID,
        account: Account,
        db: AsyncSession,
        manager: BuiltinAppManager,
    ) -> App:
        """将指定的内置应用添加到个人空间"""
        builtin_app = manager.get_builtin_app(str(builtin_app_id))
        if not builtin_app:
            raise NotFoundException("该内置应用不存在，请核实后重试")

        dumped = builtin_app.model_dump(include={"name", "description"})
        dumped["icon"] = BuiltinAppService.builtin_app_icon_url(builtin_app.id)
        app = App(
            account_id=account.id,
            status=AppStatus.DRAFT,
            **dumped,
        )
        db.add(app)
        await db.flush()

        from app.services.user_model_service import UserModelService, sanitize_chat_parameters

        model_config = await UserModelService.default_chat_model_config(account, db)
        builtin_params = (builtin_app.language_model_config or {}).get("parameters")
        if builtin_params:
            model_config["parameters"] = sanitize_chat_parameters(builtin_params)

        draft_app_config = AppConfigVersion(
            app_id=app.id,
            version=0,
            config_type=AppConfigType.DRAFT,
            model_config=model_config,
            **builtin_app.model_dump(include={
                "dialog_round", "preset_prompt", "tools", "retrieval_config", "long_term_memory",
                "opening_statement", "opening_questions", "speech_to_text", "text_to_speech",
                "review_config", "suggested_after_answer",
            }),
        )
        db.add(draft_app_config)
        await db.flush()

        app.draft_app_config_id = draft_app_config.id
        await db.commit()
        await db.refresh(app)
        return app
