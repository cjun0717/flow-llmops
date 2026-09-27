#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置应用分类实体。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CategoryEntity(BaseModel):
    """内置应用分类实体"""
    category: str = Field(default="")  # 分类唯一标识
    name: str = Field(default="")  # 分类对应的名称
