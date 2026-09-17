#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/12/01 11:49
@Author  : thezehui@gmail.com
@File    : completion.py
"""

from langchain_openai import OpenAI

from app.core.language_model.entities.model_entity import BaseLanguageModel


class Completion(OpenAI, BaseLanguageModel):
    """OpenAI聊天模型基类"""
    pass
