#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用户模型目录服务。"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.language_model.entities.default_model_parameter_template import (
    DEFAULT_MODEL_PARAMETER_TEMPLATE,
)
from app.core.language_model.entities.model_entity import (
    DefaultModelParameterName,
    ModelFeature,
    ModelParameterType,
)
from app.core.language_model.openai_compatible import OpenAICompatibleChat
from app.core.observability import langfuse_callbacks
from app.entities.app_entity import DEFAULT_CHAT_PARAMETERS
from app.exceptions import FailException, NotFoundException, ValidateException
from app.models.account import Account
from app.models.app import App, AppConfig, AppConfigVersion
from app.models.dataset import Dataset
from app.models.user_model import UserModel, UserModelType
from app.models.workflow import Workflow
from app.schemas.user_model import CreateUserModelReq, UpdateUserModelReq, UserModelItem
from app.services.embeddings_service import EmbeddingsService

ALLOWED_FEATURES = {
    ModelFeature.TOOL_CALL.value,
    ModelFeature.AGENT_THOUGHT.value,
    ModelFeature.IMAGE_INPUT.value,
}

logger = logging.getLogger(__name__)


def sanitize_chat_parameters(origin: Any) -> dict[str, Any]:
    """按 OpenAI 通用参数模板清洗推理参数。"""
    if not isinstance(origin, dict):
        origin = {}
    cleaned: dict[str, Any] = {}
    for name, spec in DEFAULT_MODEL_PARAMETER_TEMPLATE.items():
        key = name.value if isinstance(name, DefaultModelParameterName) else str(name)
        default = DEFAULT_CHAT_PARAMETERS.get(key, spec.get("default"))
        value = origin.get(key, default)
        expected = spec.get("type")
        if expected == ModelParameterType.FLOAT:
            try:
                value = float(value) if value is not None else default
            except (TypeError, ValueError):
                value = default
        elif expected == ModelParameterType.INT:
            try:
                value = int(value) if value is not None else default
            except (TypeError, ValueError):
                value = default
        min_v, max_v = spec.get("min"), spec.get("max")
        if isinstance(value, (int, float)):
            if min_v is not None and value < min_v:
                value = default
            if max_v is not None and value > max_v:
                value = default
        cleaned[key] = value if value is not None else DEFAULT_CHAT_PARAMETERS.get(key)
    return cleaned


def build_chat_model(record: UserModel, parameters: dict[str, Any] | None = None):
    """根据用户模型记录构造 Chat 实例。"""
    params = sanitize_chat_parameters({**(record.parameters or {}), **(parameters or {})})
    features = [
        ModelFeature(f) for f in (record.features or []) if f in ALLOWED_FEATURES
    ]
    return OpenAICompatibleChat(
        model=record.model_serve_name,
        api_key=record.api_key or "EMPTY",
        base_url=record.base_url or None,
        features=features,
        metadata={},
        callbacks=langfuse_callbacks(),
        **params,
    )


class UserModelService:
    """用户模型 CRUD / 默认 / 探测。"""

    @staticmethod
    async def list_models(
        account: Account,
        db: AsyncSession,
        model_type: str | None = None,
    ) -> list[UserModelItem]:
        stmt = select(UserModel).where(UserModel.account_id == account.id)
        if model_type:
            stmt = stmt.where(UserModel.model_type == model_type)
        stmt = stmt.order_by(UserModel.created_at.asc())
        result = await db.execute(stmt)
        return [UserModelItem.from_model(item) for item in result.scalars().all()]

    @staticmethod
    async def get_owned(
        model_id: UUID, account: Account, db: AsyncSession
    ) -> UserModel:
        result = await db.execute(select(UserModel).where(UserModel.id == model_id))
        record = result.scalar_one_or_none()
        if record is None or record.account_id != account.id:
            raise NotFoundException("该模型不存在")
        return record

    @staticmethod
    async def get_default(
        account_id: UUID, model_type: str, db: AsyncSession
    ) -> UserModel | None:
        result = await db.execute(
            select(UserModel).where(
                UserModel.account_id == account_id,
                UserModel.model_type == model_type,
                UserModel.is_default.is_(True),
            )
        )
        record = result.scalar_one_or_none()
        if record:
            return record
        result = await db.execute(
            select(UserModel)
            .where(
                UserModel.account_id == account_id,
                UserModel.model_type == model_type,
            )
            .order_by(UserModel.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def get_default_sync(account_id: UUID, model_type: str, db: Session) -> UserModel | None:
        record = db.execute(
            select(UserModel).where(
                UserModel.account_id == account_id,
                UserModel.model_type == model_type,
                UserModel.is_default.is_(True),
            )
        ).scalar_one_or_none()
        if record:
            return record
        return db.execute(
            select(UserModel)
            .where(
                UserModel.account_id == account_id,
                UserModel.model_type == model_type,
            )
            .order_by(UserModel.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()

    @staticmethod
    def get_by_id_sync(model_id: UUID, db: Session) -> UserModel | None:
        return db.get(UserModel, model_id)

    @staticmethod
    async def default_chat_model_config(account: Account, db: AsyncSession) -> dict[str, Any]:
        record = await UserModelService.get_default(account.id, UserModelType.CHAT, db)
        if record is None:
            return {
                "user_model_id": "",
                "parameters": dict(DEFAULT_CHAT_PARAMETERS),
            }
        return {
            "user_model_id": str(record.id),
            "parameters": sanitize_chat_parameters(record.parameters),
        }

    @staticmethod
    def _validate_req_fields(model_type: str, req: CreateUserModelReq | UpdateUserModelReq, record: UserModel | None = None) -> None:
        serve = getattr(req, "model_serve_name", None) or (record.model_serve_name if record else "")
        base_url = getattr(req, "base_url", None) or (record.base_url if record else "")
        if not serve:
            raise ValidateException("模型服务名称不能为空")
        if not base_url:
            raise ValidateException("Base URL 不能为空")
        if model_type == UserModelType.EMBEDDING:
            dimension = req.dimension if req.dimension is not None else (record.dimension if record else None)
            if not dimension:
                raise ValidateException("向量模型必须填写维度")
        if model_type == UserModelType.CHAT:
            context_window = req.context_window if req.context_window is not None else (record.context_window if record else None)
            if not context_window:
                raise ValidateException("对话模型必须填写上下文长度")
        features = req.features if req.features is not None else (record.features if record else [])
        extra = set(features or []) - ALLOWED_FEATURES
        if extra:
            raise ValidateException(f"不支持的模型能力: {', '.join(sorted(extra))}")

    @staticmethod
    def _verify_connection(record: UserModel) -> None:
        if record.model_type == UserModelType.CHAT:
            llm = build_chat_model(record, {"max_tokens": 8, "temperature": 0})
            llm.invoke("hello")
            return
        embeddings = EmbeddingsService.from_user_model(record, redis=None)
        vector = embeddings.embeddings.embed_query("hello")
        if record.dimension and len(vector) != record.dimension:
            raise ValidateException(
                f"向量维度不匹配：服务返回 {len(vector)}，配置为 {record.dimension}"
            )

    @staticmethod
    async def _clear_other_defaults(
        account_id: UUID, model_type: str, keep_id: UUID | None, db: AsyncSession
    ) -> None:
        result = await db.execute(
            select(UserModel).where(
                UserModel.account_id == account_id,
                UserModel.model_type == model_type,
                UserModel.is_default.is_(True),
            )
        )
        for item in result.scalars().all():
            if keep_id is None or item.id != keep_id:
                item.is_default = False

    @staticmethod
    async def create_model(
        req: CreateUserModelReq, account: Account, db: AsyncSession
    ) -> UserModel:
        UserModelService._validate_req_fields(req.model_type, req)
        existing = await db.execute(
            select(UserModel).where(
                UserModel.account_id == account.id,
                UserModel.model_type == req.model_type,
            )
        )
        others = existing.scalars().all()
        is_default = req.is_default or len(others) == 0
        record = UserModel(
            account_id=account.id,
            name=req.name,
            model_type=req.model_type,
            provider="openai_compatible",
            base_url=req.base_url,
            api_key=req.api_key,
            model_serve_name=req.model_serve_name,
            context_window=req.context_window,
            max_length=req.max_length,
            dimension=req.dimension,
            features=list(req.features or []),
            parameters=sanitize_chat_parameters(req.parameters)
            if req.model_type == UserModelType.CHAT
            else {},
            is_default=is_default,
        )
        if req.verify:
            try:
                UserModelService._verify_connection(record)
            except ValidateException:
                raise
            except Exception as exc:
                logger.exception("模型连通性检查失败")
                raise ValidateException(f"调用模型失败：{exc}") from exc
        if is_default:
            await UserModelService._clear_other_defaults(
                account.id, req.model_type, None, db
            )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def update_model(
        model_id: UUID, req: UpdateUserModelReq, account: Account, db: AsyncSession
    ) -> UserModel:
        record = await UserModelService.get_owned(model_id, account, db)
        UserModelService._validate_req_fields(record.model_type, req, record)
        if req.name is not None:
            record.name = req.name.strip()
        if req.base_url is not None:
            record.base_url = req.base_url
        if req.api_key:
            record.api_key = req.api_key.strip()
        if req.model_serve_name is not None:
            record.model_serve_name = req.model_serve_name.strip()
        if req.context_window is not None:
            record.context_window = req.context_window
        if req.max_length is not None:
            record.max_length = req.max_length
        if req.dimension is not None:
            record.dimension = req.dimension
        if req.features is not None:
            record.features = list(req.features)
        if req.parameters is not None and record.model_type == UserModelType.CHAT:
            record.parameters = sanitize_chat_parameters(req.parameters)
        if req.is_default is True:
            await UserModelService._clear_other_defaults(
                account.id, record.model_type, record.id, db
            )
            record.is_default = True
        if req.verify:
            try:
                UserModelService._verify_connection(record)
            except ValidateException:
                raise
            except Exception as exc:
                raise ValidateException(f"调用模型失败：{exc}") from exc
        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def set_default(
        model_id: UUID, account: Account, db: AsyncSession
    ) -> UserModel:
        record = await UserModelService.get_owned(model_id, account, db)
        await UserModelService._clear_other_defaults(
            account.id, record.model_type, record.id, db
        )
        record.is_default = True
        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def _assert_not_referenced(record: UserModel, db: AsyncSession) -> None:
        needle = str(record.id)
        if record.model_type == UserModelType.EMBEDDING:
            result = await db.execute(
                select(Dataset.id).where(Dataset.embedding_model_id == record.id).limit(1)
            )
            if result.scalar_one_or_none() is not None:
                raise FailException("该向量模型已被知识库使用，无法删除")
            return

        # JSONB 包含查询，避免全表扫描 Python
        draft_result = await db.execute(
            select(AppConfigVersion.id)
            .join(App, App.id == AppConfigVersion.app_id)
            .where(AppConfigVersion.model_config.contains({"user_model_id": needle}))
            .limit(1)
        )
        if draft_result.scalar_one_or_none() is not None:
            raise FailException("该对话模型仍被应用草稿或发布配置引用，无法删除")
        pub_result = await db.execute(
            select(AppConfig.id)
            .join(App, App.id == AppConfig.app_id)
            .where(AppConfig.model_config.contains({"user_model_id": needle}))
            .limit(1)
        )
        if pub_result.scalar_one_or_none() is not None:
            raise FailException("该对话模型仍被已发布应用引用，无法删除")
        wf_result = await db.execute(select(Workflow.graph))
        for graph in wf_result.scalars().all():
            nodes = (graph or {}).get("nodes") or []
            for node in nodes:
                data = node.get("data") or node
                cfg = data.get("language_model_config") or data.get("model_config") or {}
                if str(cfg.get("user_model_id") or "") == needle:
                    raise FailException("该对话模型仍被工作流引用，无法删除")

    @staticmethod
    async def delete_model(
        model_id: UUID, account: Account, db: AsyncSession
    ) -> None:
        record = await UserModelService.get_owned(model_id, account, db)
        await UserModelService._assert_not_referenced(record, db)
        was_default = record.is_default
        model_type = record.model_type
        await db.delete(record)
        await db.flush()
        if was_default:
            nxt = await UserModelService.get_default(account.id, model_type, db)
            if nxt:
                nxt.is_default = True
        await db.commit()

    @staticmethod
    async def probe(base_url: str, api_key: str) -> list[dict[str, Any]]:
        url = f"{base_url.rstrip('/')}/models"
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as exc:
            text = exc.response.text[:200] if exc.response is not None else str(exc)
            status = exc.response.status_code if exc.response is not None else "?"
            raise ValidateException(f"探测失败: HTTP {status} {text}") from exc
        except Exception as exc:
            raise ValidateException(f"探测失败：{exc}") from exc

        raw_models = data.get("data") if isinstance(data, dict) else None
        if not isinstance(raw_models, list):
            raise ValidateException(f"返回格式异常: {str(data)[:200]}")
        models = []
        for item in raw_models:
            if isinstance(item, dict) and item.get("id"):
                models.append({"id": item.get("id")})
        return models

    @staticmethod
    def resolve_embedding_sync(dataset: Dataset, db: Session) -> UserModel:
        record = None
        if dataset.embedding_model_id:
            record = db.get(UserModel, dataset.embedding_model_id)
        if record is None:
            record = UserModelService.get_default_sync(
                dataset.account_id, UserModelType.EMBEDDING, db
            )
        if record is None:
            raise FailException("请先在模型管理中添加向量模型")
        if not record.dimension:
            raise FailException("向量模型未配置维度")
        return record
