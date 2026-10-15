#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DuckDuckGo 搜索工具（直接使用 duckduckgo-search 库）。"""
from __future__ import annotations

from typing import Optional, Type

from duckduckgo_search import DDGS
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.lib.helper import add_attribute


class DDGInput(BaseModel):
    query: str = Field(description="需要搜索的查询语句")


class DuckDuckGoSearchTool(BaseTool):
    """DuckDuckGo 搜索工具（返回 标题/链接/摘要 文本）。"""

    name: str = "duckduckgo_search"
    description: str = (
        "一个注重隐私的搜索工具，当你需要搜索时事时可以使用该工具，"
        "工具的输入是一个查询语句"
    )
    args_schema: Type[BaseModel] = DDGInput
    max_results: int = 5

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            results = DDGS().text(query, max_results=self.max_results)
        except Exception as e:
            raise ValueError(f"DuckDuckGo 搜索出错: {e}") from e
        return "\n\n".join(
            f"{result['title']}\n{result['href']}\n{result['body']}" for result in results
        )


@add_attribute("args_schema", DDGInput)
def duckduckgo_search(**kwargs) -> BaseTool:
    """返回 DuckDuckGo 搜索工具"""
    return DuckDuckGoSearchTool()