#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置工具分类管理器（读取 categories.yaml + icons/*.svg）。"""
from __future__ import annotations

import os.path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.core.tools.builtin_tools.entities import CategoryEntity
from app.exceptions import NotFoundException


class BuiltinCategoryManager(BaseModel):
    """内置工具分类管理器（单例）"""

    category_map: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_categories()

    def get_category_map(self) -> dict[str, Any]:
        """获取分类映射"""
        return self.category_map

    def _init_categories(self) -> None:
        """初始化分类数据"""
        if self.category_map:
            return

        current_path = os.path.abspath(__file__)
        category_path = os.path.dirname(current_path)
        category_yaml_path = os.path.join(category_path, "categories.yaml")
        with open(category_yaml_path, encoding="utf-8") as f:
            categories = yaml.safe_load(f)

        for category in categories:
            category_entity = CategoryEntity(**category)
            icon_path = os.path.join(category_path, "icons", category_entity.icon)
            if not os.path.exists(icon_path):
                raise NotFoundException(f"该分类{category_entity.category}的icon未提供")
            with open(icon_path, encoding="utf-8") as f:
                icon = f.read()
            self.category_map[category_entity.category] = {
                "entity": category_entity,
                "icon": icon,
            }
