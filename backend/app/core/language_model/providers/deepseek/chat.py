#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/02/01 2:40
@Author  : thezehui@gmail.com
@File    : chat.py
"""
import os
from typing import Tuple

import tiktoken
from langchain_deepseek import ChatDeepSeek

from app.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatDeepSeek, BaseLanguageModel):
    """深度求索大语言模型基类"""

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_API_BASE"),
            **kwargs
        )

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """重写月之暗面获取编码模型名字+模型函数，该类继承OpenAI，词表模型可以使用gpt-3.5-turbo防止出错"""
        # 1.将DeepSeek的词表模型设置为gpt-3.5-turbo
        model = "gpt-3.5-turbo"

        # 2.返回模型名字+编码�?        return model, tiktoken.encoding_for_model(model)
