#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置应用广场 Pydantic schema（迁移自 imooc builtin_app_schema.py）。"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.builtin_apps.entities.builtin_app_entity import BuiltinAppEntity
from app.core.builtin_apps.entities.category_entity import CategoryEntity


class GetBuiltinAppCategoriesResp(BaseModel):
    """获取内置应用分类列表响应"""
    category: str = ""
    name: str = ""

    @classmethod
    def from_entity(cls, data: CategoryEntity) -> "GetBuiltinAppCategoriesResp":
        return cls(category=data.category, name=data.name)


class GetBuiltinAppsResp(BaseModel):
    """获取内置应用实体列表响应"""
    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    category: str = ""
    name: str = ""
    icon: str = ""
    description: str = ""
    model_config_data: dict = Field(default_factory=dict, alias="model_config")
    created_at: int = 0

    @classmethod
    def from_entity(cls, data: BuiltinAppEntity) -> "GetBuiltinAppsResp":
        return cls(
            id=data.id,
            category=data.category,
            name=data.name,
            icon=data.icon,
            description=data.description,
            model_config_data={
                "provider": data.language_model_config.get("provider", ""),
                "model": data.language_model_config.get("model", ""),
            },
            created_at=data.created_at,
        )


class AddBuiltinAppToSpaceReq(BaseModel):
    """添加内置应用到个人空间请求"""
    builtin_app_id: UUID = Field(..., description="内置应用id")


class AddBuiltinAppToSpaceData(BaseModel):
    """添加内置应用到个人空间返回数据"""
    id: UUID
