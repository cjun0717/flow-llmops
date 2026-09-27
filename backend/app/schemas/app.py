#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用模块 Schema。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
class GetPublishHistoriesWithPageReq(PageParams):
    """获取应用发布历史配置分页列表请求"""
    pass


class FallbackHistoryToDraftReq(BaseModel):
    """回退历史版本到草稿请求"""
    app_config_version_id: UUID = Field(..., description="回退配置版本id")


class UpdateDraftAppConfigReq(BaseModel):
    """更新应用草稿配置请求（字段均为可选，至少传一个）"""
    model_config = ConfigDict(populate_by_name=True)

    model_config_: dict | None = Field(default=None, alias="model_config", description="模型配置")
    dialog_round: int | None = Field(default=None, ge=0, le=100, description="携带上下文轮数")
    preset_prompt: str | None = Field(default=None, max_length=2000, description="人设与回复逻辑")
    tools: list[dict] | None = Field(default=None, description="工具列表")
    workflows: list[str] | None = Field(default=None, description="工作流id列表")
    datasets: list[str] | None = Field(default=None, description="知识库id列表")
    retrieval_config: dict | None = Field(default=None, description="检索配置")
    long_term_memory: dict | None = Field(default=None, description="长期记忆配置")
    opening_statement: str | None = Field(default=None, max_length=2000, description="开场白")
    opening_questions: list[str] | None = Field(default=None, description="开场建议问题")
    speech_to_text: dict | None = Field(default=None, description="语音转文本")
    text_to_speech: dict | None = Field(default=None, description="文本转语音")
    suggested_after_answer: dict | None = Field(default=None, description="回答后建议问题")
    review_config: dict | None = Field(default=None, description="审核配置")


class PublishHistoryItem(BaseModel):
    """发布历史列表项"""
    id: UUID
    version: int
    created_at: int

    @classmethod
    def from_model(cls, v: AppConfigVersion) -> "PublishHistoryItem":
        return cls(
            id=v.id,
            version=v.version,
            created_at=_datetime_to_timestamp(v.created_at),
        )


class PublishedConfigData(BaseModel):
    """已发布 WebApp 配置"""
    web_app: dict
