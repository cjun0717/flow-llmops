#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""语言模型运行时服务：从账号自己添加的用户模型加载对话实例。"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.exceptions import FailException
from app.models.user_model import UserModel, UserModelType


class LanguageModelService:
    """按用户模型目录加载对话模型。"""

    def load_language_model(self, model_config: dict[str, Any]):
        """根据用户模型 id 加载对话实例。"""
        from app.db import SyncSessionLocal
        from app.services.user_model_service import build_chat_model, sanitize_chat_parameters

        user_model_id = (model_config or {}).get("user_model_id") or ""
        if not user_model_id:
            raise FailException("请先在模型管理中添加对话模型")
        try:
            uid = UUID(str(user_model_id))
        except Exception as exc:
            raise FailException("请先在模型管理中添加对话模型") from exc

        with SyncSessionLocal() as db:
            record = db.get(UserModel, uid)
            if record is None or record.model_type != UserModelType.CHAT:
                raise FailException("请先在模型管理中添加对话模型")
            parameters = sanitize_chat_parameters((model_config or {}).get("parameters") or {})
            return build_chat_model(record, parameters)

    def load_default_language_model(self, account_id: UUID | None = None):
        """加载账号默认对话模型。"""
        from app.db import SyncSessionLocal
        from app.services.user_model_service import UserModelService, build_chat_model

        if account_id is None:
            raise FailException("请先在模型管理中添加对话模型")
        with SyncSessionLocal() as db:
            record = UserModelService.get_default_sync(account_id, UserModelType.CHAT, db)
            if record is None:
                raise FailException("请先在模型管理中添加对话模型")
            return build_chat_model(record)
