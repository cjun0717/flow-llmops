#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/12/01 11:48
@Author  : thezehui@gmail.com
@File    : chat.py
"""

from langchain_openai import ChatOpenAI

from app.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOpenAI, BaseLanguageModel):
    """OpenAI聊天模型基类"""
    pass
