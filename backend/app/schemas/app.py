#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用模块 Schema。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.app import App, AppConfigVersion
from app.schemas.response import PageParams


def _datetime_to_timestamp(dt: datetime | None) -> int:
    if dt is None:
        return 0
    return int(dt.timestamp())


class CreateAppReq(BaseModel):
    """创建应用请求"""
    name: str = Field(..., min_length=1, max_length=40, description="应用名称")
    icon: str = Field(..., min_length=1, description="应用图标URL")
    description: str = Field("", max_length=800, description="应用描述")


class UpdateAppReq(BaseModel):
    """修改应用请求"""
    name: str = Field(..., min_length=1, max_length=40, description="应用名称")
    icon: str = Field(..., min_length=1, description="应用图标URL")
    description: str = Field("", max_length=800, description="应用描述")


class GetAppsWithPageReq(PageParams):
    """应用分页列表请求"""
    search_word: str = Field("", description="搜索词")


class AppListItemData(BaseModel):
    """应用列表项"""
    id: UUID
    name: str
    icon: str
    description: str
    preset_prompt: str
    model_config_data: dict = Field(default_factory=dict, alias="model_config")
    status: str
    updated_at: int
    created_at: int

    @classmethod
    def from_model(cls, app: App, config: AppConfigVersion) -> "AppListItemData":
        return cls(
            id=app.id,
            name=app.name,
            icon=app.icon,
            description=app.description,
            preset_prompt=config.preset_prompt,
            model_config_data={
                "provider": (config.model_config or {}).get("provider", ""),
                "model": (config.model_config or {}).get("model", ""),
            },
            status=app.status,
            updated_at=_datetime_to_timestamp(app.updated_at),
            created_at=_datetime_to_timestamp(app.created_at),
        )


class AppDetailData(BaseModel):
    """应用详情"""
    id: UUID
    debug_conversation_id: str = ""
    name: str
    icon: str
    description: str
    status: str
    draft_updated_at: int
    updated_at: int
    created_at: int

    @classmethod
    def from_model(cls, app: App, draft_config: AppConfigVersion) -> "AppDetailData":
        return cls(
            id=app.id,
            debug_conversation_id=str(app.debug_conversation_id) if app.debug_conversation_id else "",
            name=app.name,
            icon=app.icon,
            description=app.description,
            status=app.status,
            draft_updated_at=_datetime_to_timestamp(draft_config.updated_at),
            updated_at=_datetime_to_timestamp(app.updated_at),
            created_at=_datetime_to_timestamp(app.created_at),
        )


class CreateAppData(BaseModel):
    """创建/复制应用响应"""
    id: UUID
