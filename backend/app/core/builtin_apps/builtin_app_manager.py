#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置应用管理器：读取 yaml 构建分类与应用映射。"""
from __future__ import annotations

import os

import yaml
from pydantic import BaseModel, Field

from app.core.builtin_apps.entities.builtin_app_entity import BuiltinAppEntity
from app.core.builtin_apps.entities.category_entity import CategoryEntity


class BuiltinAppManager(BaseModel):
    """内置应用管理器"""
    builtin_app_map: dict[str, BuiltinAppEntity] = Field(default_factory=dict)
    categories: list[CategoryEntity] = Field(default_factory=list)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_categories()
        self._init_builtin_app_map()

    def get_builtin_app(self, builtin_app_id: str) -> BuiltinAppEntity | None:
        """根据 id 获取内置应用信息"""
        return self.builtin_app_map.get(builtin_app_id)

    def get_builtin_apps(self) -> list[BuiltinAppEntity]:
        """获取内置应用实体列表"""
        return list(self.builtin_app_map.values())

    def get_categories(self) -> list[CategoryEntity]:
        """获取内置应用分类列表"""
        return self.categories

    def _init_builtin_app_map(self) -> None:
        """读取 builtin_apps/*.yaml 初始化应用映射"""
        if self.builtin_app_map:
            return

        current_path = os.path.abspath(__file__)
        parent_path = os.path.dirname(current_path)
        builtin_apps_yaml_path = os.path.join(parent_path, "builtin_apps")

        for filename in os.listdir(builtin_apps_yaml_path):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                file_path = os.path.join(builtin_apps_yaml_path, filename)
                with open(file_path, encoding="utf-8") as f:
                    builtin_app = yaml.safe_load(f)

                builtin_app["language_model_config"] = builtin_app.pop("model_config")
                self.builtin_app_map[builtin_app.get("id")] = BuiltinAppEntity(**builtin_app)

    def _init_categories(self) -> None:
        """读取 categories/categories.yaml 初始化分类"""
        if self.categories:
            return

        current_path = os.path.abspath(__file__)
        parent_path = os.path.dirname(current_path)
        categories_yaml_path = os.path.join(parent_path, "categories", "categories.yaml")

        with open(categories_yaml_path, encoding="utf-8") as f:
            categories = yaml.safe_load(f)

        for category in categories:
            self.categories.append(CategoryEntity(**category))
