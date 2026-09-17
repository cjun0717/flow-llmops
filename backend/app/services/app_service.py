#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用服务（CRUD 部分）。"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.app_entity import AppStatus, AppConfigType, DEFAULT_APP_CONFIG
from app.exceptions import ForbiddenException, NotFoundException
from app.models.account import Account
from app.models.app import App, AppConfigVersion
from app.schemas.app import (
    AppDetailData,
    AppListItemData,
    CreateAppReq,
    GetAppsWithPageReq,
    UpdateAppReq,
)
from app.schemas.response import PageData, page_data


class AppService:
    """应用 CRUD"""

    @staticmethod
    async def _get_draft_config(app_id: UUID, db: AsyncSession) -> AppConfigVersion:
        """获取应用的草稿配置（替代原始 @property 查库逻辑）"""
        result = await db.execute(
            select(AppConfigVersion).where(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.DRAFT,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_or_create_draft_config(
        app_id: UUID, db: AsyncSession
    ) -> AppConfigVersion:
        """获取草稿配置，不存在则创建默认配置"""
        config = await AppService._get_draft_config(app_id, db)
        if config is not None:
            return config
        config = AppConfigVersion(
            app_id=app_id,
            version=0,
            config_type=AppConfigType.DRAFT,
            **DEFAULT_APP_CONFIG,
        )
        db.add(config)
        await db.flush()
        return config

    @staticmethod
    async def get_app(app_id: UUID, account: Account, db: AsyncSession) -> App:
        """获取应用并校验权限"""
        result = await db.execute(select(App).where(App.id == app_id))
        app = result.scalar_one_or_none()
        if not app:
            raise NotFoundException("该应用不存在，请核实后重试")
        if app.account_id != account.id:
            raise ForbiddenException("当前账号无权限访问该应用，请核实后尝试")
        return app

    @staticmethod
    async def create_app(
        req: CreateAppReq, account: Account, db: AsyncSession
    ) -> App:
        """创建应用 + 草稿配置"""
        app = App(
            account_id=account.id,
            name=req.name,
            icon=req.icon,
            description=req.description,
            status=AppStatus.DRAFT,
        )
        db.add(app)
        await db.flush()

        config = AppConfigVersion(
            app_id=app.id,
            version=0,
            config_type=AppConfigType.DRAFT,
            **DEFAULT_APP_CONFIG,
        )
        db.add(config)
        await db.flush()

        app.draft_app_config_id = config.id
        await db.commit()
        await db.refresh(app)
        return app

    @staticmethod
    async def update_app(
        app_id: UUID, req: UpdateAppReq, account: Account, db: AsyncSession
    ) -> None:
        """修改应用基础信息"""
        app = await AppService.get_app(app_id, account, db)
        app.name = req.name
        app.icon = req.icon
        app.description = req.description
        await db.commit()

    @staticmethod
    async def delete_app(app_id: UUID, account: Account, db: AsyncSession) -> None:
        """删除应用"""
        app = await AppService.get_app(app_id, account, db)
        await db.delete(app)
        await db.commit()

    @staticmethod
    async def copy_app(app_id: UUID, account: Account, db: AsyncSession) -> App:
        """复制应用 + 草稿配置"""
        app = await AppService.get_app(app_id, account, db)
        draft_config = await AppService._get_or_create_draft_config(app_id, db)

        new_app = App(
            account_id=app.account_id,
            name=app.name,
            icon=app.icon,
            description=app.description,
            status=AppStatus.DRAFT,
        )
        db.add(new_app)
        await db.flush()

        new_config = AppConfigVersion(
            app_id=new_app.id,
            version=0,
            config_type=AppConfigType.DRAFT,
            model_config=draft_config.model_config,
            dialog_round=draft_config.dialog_round,
            preset_prompt=draft_config.preset_prompt,
            tools=draft_config.tools,
            workflows=draft_config.workflows,
            datasets=draft_config.datasets,
            retrieval_config=draft_config.retrieval_config,
            long_term_memory=draft_config.long_term_memory,
            opening_statement=draft_config.opening_statement,
            opening_questions=draft_config.opening_questions,
            speech_to_text=draft_config.speech_to_text,
            text_to_speech=draft_config.text_to_speech,
            suggested_after_answer=draft_config.suggested_after_answer,
            review_config=draft_config.review_config,
        )
        db.add(new_config)
        await db.flush()

        new_app.draft_app_config_id = new_config.id
        await db.commit()
        await db.refresh(new_app)
        return new_app

    @staticmethod
    async def get_apps_with_page(
        req: GetAppsWithPageReq, account: Account, db: AsyncSession
    ) -> PageData[AppListItemData]:
        """应用分页列表"""
        filters = [App.account_id == account.id]
        if req.search_word:
            filters.append(App.name.ilike(f"%{req.search_word}%"))

        # 总数
        count_result = await db.execute(
            select(func.count()).select_from(App).where(*filters)
        )
        total_record = count_result.scalar() or 0

        # 分页数据
        result = await db.execute(
            select(App)
            .where(*filters)
            .order_by(desc(App.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        apps = result.scalars().all()

        # 批量获取草稿配置
        items: list[AppListItemData] = []
        for app in apps:
            config = await AppService._get_or_create_draft_config(app.id, db)
            items.append(AppListItemData.from_model(app, config))

        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @staticmethod
    async def get_app_detail(
        app_id: UUID, account: Account, db: AsyncSession
    ) -> AppDetailData:
        """应用详情"""
        app = await AppService.get_app(app_id, account, db)
        draft_config = await AppService._get_or_create_draft_config(app_id, db)
        return AppDetailData.from_model(app, draft_config)
