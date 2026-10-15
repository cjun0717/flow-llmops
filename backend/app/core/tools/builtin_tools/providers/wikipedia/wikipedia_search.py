#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""维基百科搜索工具（直接使用 wikipedia 库）。"""
from __future__ import annotations

from typing import Optional, Type

import wikipedia
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.lib.helper import add_attribute


class WikipediaQueryInput(BaseModel):
    query: str = Field(description="维基百科搜索的查询语句")


class WikipediaAPIWrapper:
    """wikipedia 库薄封装，行为对齐原 community 实现。"""

    def __init__(self, top_k_results: int = 2, doc_content_chars_max: int = 4000) -> None:
        self.top_k_results = top_k_results
        self.doc_content_chars_max = doc_content_chars_max

    def run(self, query: str) -> str:
        try:
            page_titles = wikipedia.search(query)
        except Exception as e:
            raise ValueError(f"维基百科搜索出错: {e}") from e
        if not page_titles:
            return "没有找到相关内容"
        docs: list[str] = []
        for title in page_titles[: self.top_k_results]:
            try:
                page = wikipedia.page(title, auto_suggest=True, redirect=True)
            except (
                wikipedia.exceptions.PageError,
                wikipedia.exceptions.DisambiguationError,
            ):
                continue
            summary = page.summary[: self.doc_content_chars_max]
            if "may refer to" in summary:
                continue
            docs.append(f"Title: {page.title}\nURL: {page.url}\nSummary: {summary}")
        return "\n\n".join(docs) if docs else "没有找到相关内容"


class WikipediaSearchTool(BaseTool):
    """维基百科搜索工具。"""

    name: str = "wikipedia"
    description: str = (
        "一个维基百科搜索工具，当你需要查找公共知识或事实性信息时可以使用该工具，"
        "该工具的输入是一个查询语句"
    )
    args_schema: Type[BaseModel] = WikipediaQueryInput
    api_wrapper: WikipediaAPIWrapper

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        return self.api_wrapper.run(query)


@add_attribute("args_schema", WikipediaQueryInput)
def wikipedia_search(**kwargs) -> BaseTool:
    """返回维基百科搜索工具"""
    return WikipediaSearchTool(api_wrapper=WikipediaAPIWrapper())