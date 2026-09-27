#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""获取当前时间工具。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel


class CurrentTimeArgsSchema(BaseModel):
    """当前时间工具无输入参数。"""

    pass


class CurrentTimeTool(BaseTool):
    """一个用于获取当前时间的工具"""

    name: str = "current_time"
    description: str = "一个用于获取当前时间的工具"
    args_schema: type[BaseModel] = CurrentTimeArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")


def current_time(**kwargs) -> BaseTool:
    """返回获取当前时间的 LangChain 工具"""
    return CurrentTimeTool()
