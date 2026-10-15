#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""谷歌 Serper 搜索工具（直接调用 https://google.serper.dev/search API）。"""
from __future__ import annotations

import os
from typing import Any, Optional, Type

import requests
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.lib.helper import add_attribute


class GoogleSerperArgsSchema(BaseModel):
    """谷歌 SerperAPI 搜索参数描述"""

    query: str = Field(description="需要检索查询的语句.")


class GoogleSerperAPIWrapper:
    """Serper.dev 谷歌搜索 API 薄封装，凭证沿用环境变量 SERPER_API_KEY。"""

    def __init__(self, api_key: str | None = None, k: int = 10) -> None:
        self.api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        self.k = k

    def run(self, query: str) -> str:
        if not self.api_key:
            raise ValueError("缺少 SERPER_API_KEY，无法使用谷歌搜索工具")
        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            json={"q": query, "num": self.k},
            timeout=30,
        )
        response.raise_for_status()
        results: dict[str, Any] = response.json()
        return self._to_text(results)

    def _to_text(self, results: dict[str, Any]) -> str:
        snippets: list[str] = []
        if "answerBox" in results:
            box = results["answerBox"]
            answer = box.get("answer") or box.get("snippet") or ""
            if answer:
                snippets.append(f"{answer}")
        for result in results.get("organic", [])[: self.k]:
            snippets.append(
                f"Text: {result.get('title', '')}\nLink: {result.get('link', '')}\n"
                f"Snippet: {result.get('snippet', '')}"
            )
        return "\n\n".join(snippets)


class GoogleSerperTool(BaseTool):
    """谷歌 Serper 搜索工具。"""

    name: str = "google_serper"
    description: str = (
        "这是一个低成本的谷歌搜索API。当你需要搜索时事的时候，可以使用该工具，"
        "该工具的输入是一个查询语句"
    )
    args_schema: Type[BaseModel] = GoogleSerperArgsSchema
    api_wrapper: GoogleSerperAPIWrapper

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        return self.api_wrapper.run(query)


@add_attribute("args_schema", GoogleSerperArgsSchema)
def google_serper(**kwargs) -> BaseTool:
    """谷歌 Serp 搜索"""
    return GoogleSerperTool(api_wrapper=GoogleSerperAPIWrapper())