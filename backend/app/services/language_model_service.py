#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""语言模型服务（只读部分）。"""
from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any

from app.core.language_model import LanguageModelManager
from app.exceptions import NotFoundException
from app.lib.helper import convert_model_to_dict


class LanguageModelService:
    """语言模型只读服务"""

    def __init__(self, manager: LanguageModelManager) -> None:
        self.manager = manager

    def get_language_models(self) -> list[dict[str, Any]]:
        """获取所有语言模型提供商列表"""
        providers = self.manager.get_providers()
        language_models: list[dict[str, Any]] = []
        for provider in providers:
            provider_entity = provider.provider_entity
            model_entities = provider.get_model_entities()
            language_models.append(
                {
                    "name": provider_entity.name,
                    "position": provider.position,
                    "label": provider_entity.label,
                    "icon": provider_entity.icon,
                    "description": provider_entity.description,
                    "background": provider_entity.background,
                    "support_model_types": provider_entity.supported_model_types,
                    "models": convert_model_to_dict(model_entities),
                }
            )
        return language_models

    def get_language_model(
        self, provider_name: str, model_name: str
    ) -> dict[str, Any]:
        """根据提供者名字+模型名字获取模型详细信息"""
        provider = self.manager.get_provider(provider_name)
        model_entity = provider.get_model_entity(model_name)
        return convert_model_to_dict(model_entity)

    def get_language_model_icon(self, provider_name: str) -> tuple[bytes, str]:
        """根据提供者名字获取图标（字节 + mimetype）"""
        provider = self.manager.get_provider(provider_name)

        # providers 目录：app/core/language_model/providers/{provider_name}/_asset/{icon}
        providers_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "core", "language_model", "providers", provider_name,
        )
        icon_path = os.path.join(providers_dir, "_asset", provider.provider_entity.icon)

        if not os.path.exists(icon_path):
            raise NotFoundException("该模型提供者_asset下未提供图标")

        mimetype, _ = mimetypes.guess_type(icon_path)
        mimetype = mimetype or "application/octet-stream"

        with open(icon_path, "rb") as f:
            return f.read(), mimetype

    def load_language_model(self, model_config: dict[str, Any]):
        """根据模型配置加载大语言模型实例（阶段8会话流式使用，此处预留）"""
        try:
            provider_name = model_config.get("provider", "")
            model_name = model_config.get("model", "")
            parameters = model_config.get("parameters", {})

            provider = self.manager.get_provider(provider_name)
            model_entity = provider.get_model_entity(model_name)
            model_class = provider.get_model_class(model_entity.model_type)

            return model_class(
                **model_entity.attributes,
                **parameters,
                features=model_entity.features,
                metadata=model_entity.metadata,
            )
        except Exception as error:
            logging.error("获取模型失败: %s", error, exc_info=True)
            return self.load_default_language_model()

    def load_default_language_model(self):
        """加载默认大语言模型（兜底）"""
        provider = self.manager.get_provider("openai")
        model_entity = provider.get_model_entity("gpt-4o-mini")
        model_class = provider.get_model_class(model_entity.model_type)
        return model_class(
            **model_entity.attributes,
            temperature=1,
            max_tokens=8192,
            features=model_entity.features,
            metadata=model_entity.metadata,
        )
