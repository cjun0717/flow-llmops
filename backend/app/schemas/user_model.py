#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用户模型目录 Schema。"""
from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.entities.app_entity import DEFAULT_CHAT_PARAMETERS
from app.models.user_model import UserModel


UserModelTypeLiteral = Literal["chat", "embedding"]


class CreateUserModelReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="显示名称")
    model_type: UserModelTypeLiteral = Field(..., description="chat 或 embedding")
    base_url: str = Field(..., min_length=1, max_length=1024, description="OpenAI 兼容 Base URL")
    api_key: str = Field(..., min_length=1, description="API Key")
    model_serve_name: str = Field(..., min_length=1, max_length=255, description="API model 参数")
    context_window: Optional[int] = Field(None, ge=1, description="对话上下文长度")
    max_length: Optional[int] = Field(None, ge=1, description="向量最大输入长度")
    dimension: Optional[int] = Field(None, ge=1, le=8192, description="向量维度")
    features: list[str] = Field(default_factory=list, description="对话能力开关")
    parameters: dict = Field(default_factory=dict, description="对话默认推理参数")
    is_default: bool = False
    verify: bool = Field(False, description="是否在保存前探测连通性")

    @field_validator("base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("api_key", "name", "model_serve_name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class UpdateUserModelReq(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, min_length=1, max_length=1024)
    api_key: Optional[str] = Field(None, description="留空或不传表示不修改")
    model_serve_name: Optional[str] = Field(None, min_length=1, max_length=255)
    context_window: Optional[int] = Field(None, ge=1)
    max_length: Optional[int] = Field(None, ge=1)
    dimension: Optional[int] = Field(None, ge=1, le=8192)
    features: Optional[list[str]] = None
    parameters: Optional[dict] = None
    is_default: Optional[bool] = None
    verify: bool = False

    @field_validator("base_url")
    @classmethod
    def strip_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip().rstrip("/")


class ProbeUserModelReq(BaseModel):
    base_url: str = Field(..., min_length=1)
    api_key: str = Field("", description="部分本地服务可不填")
    model_type: UserModelTypeLiteral = "chat"

    @field_validator("base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.strip().rstrip("/")


class UserModelItem(BaseModel):
    id: UUID
    name: str
    model_type: str
    provider: str
    base_url: str
    model_serve_name: str
    context_window: int | None = None
    max_length: int | None = None
    dimension: int | None = None
    features: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    is_default: bool = False
    has_api_key: bool = False
    created_at: int = 0
    updated_at: int = 0

    @classmethod
    def from_model(cls, record: UserModel) -> "UserModelItem":
        return cls(
            id=record.id,
            name=record.name,
            model_type=record.model_type,
            provider=record.provider,
            base_url=record.base_url,
            model_serve_name=record.model_serve_name,
            context_window=record.context_window,
            max_length=record.max_length,
            dimension=record.dimension,
            features=list(record.features or []),
            parameters=dict(record.parameters or DEFAULT_CHAT_PARAMETERS),
            is_default=bool(record.is_default),
            has_api_key=bool(record.api_key),
            created_at=int(record.created_at.timestamp()) if record.created_at else 0,
            updated_at=int(record.updated_at.timestamp()) if record.updated_at else 0,
        )
