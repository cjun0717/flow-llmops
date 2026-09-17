#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/12/01 1:44
@Author  : thezehui@gmail.com
@File    : chat.py
"""
from langchain_ollama import ChatOllama

from app.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOllama, BaseLanguageModel):
    """Ollama聊天模型"""
    base_url: str = "http://60.247.21.102:9432"
