#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DALLE-3 绘图工具（app/lib/dalle.py 的客户端封装为 LangChain 工具）。"""
from __future__ import annotations

from typing import Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.lib.dalle import DallEAPIWrapper
from app.lib.helper import add_attribute


class Dalle3ArgsSchema(BaseModel):
    query: str = Field(description="输入应该是生成图像的文本提示(prompt)")


class OpenAIDALLEImageGenerationTool(BaseTool):
    """DALL·E 图像生成工具，返回逗号分隔的图片 URL。"""

    name: str = "dalle3"
    description: str = "DALL·E 绘图工具，输入是生成图像的文本提示(prompt)，返回生成图片的 URL"
    args_schema: Type[BaseModel] = Dalle3ArgsSchema
    api_wrapper: DallEAPIWrapper

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        return self.api_wrapper.run(query)


@add_attribute("args_schema", Dalle3ArgsSchema)
def dalle3(**kwargs) -> BaseTool:
    """返回 dalle3 绘图的 LangChain 工具"""
    return OpenAIDALLEImageGenerationTool(
        api_wrapper=DallEAPIWrapper(model="dall-e-3", **kwargs),
    )