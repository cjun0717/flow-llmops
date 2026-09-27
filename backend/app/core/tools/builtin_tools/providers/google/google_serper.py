#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""谷歌 Serper 搜索工具。"""
from __future__ import annotations

from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.lib.helper import add_attribute


class GoogleSerperArgsSchema(BaseModel):
    """谷歌 SerperAPI 搜索参数描述"""

    query: str = Field(description="需要检索查询的语句.")


@add_attribute("args_schema", GoogleSerperArgsSchema)
def google_serper(**kwargs) -> BaseTool:
    """谷歌 Serp 搜索"""
    return GoogleSerperRun(
        name="google_serper",
        description="这是一个低成本的谷歌搜索API。当你需要搜索时事的时候，可以使用该工具，该工具的输入是一个查询语句",
        args_schema=GoogleSerperArgsSchema,
        api_wrapper=GoogleSerperAPIWrapper(),
    )
