#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DALLE-3 绘图工具。"""
from __future__ import annotations

from langchain_community.tools.openai_dalle_image_generation import (
    OpenAIDALLEImageGenerationTool,
)
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.lib.helper import add_attribute


class Dalle3ArgsSchema(BaseModel):
    query: str = Field(description="输入应该是生成图像的文本提示(prompt)")


@add_attribute("args_schema", Dalle3ArgsSchema)
def dalle3(**kwargs) -> BaseTool:
    """返回 dalle3 绘图的 LangChain 工具"""
    return OpenAIDALLEImageGenerationTool(
        api_wrapper=DallEAPIWrapper(model="dall-e-3", **kwargs),
        args_schema=Dalle3ArgsSchema,
    )
