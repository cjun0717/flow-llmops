#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenAI 兼容 Chat 封装（凭证来自用户模型目录，不读 YAML）。"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.language_model.entities.model_entity import BaseLanguageModel


class OpenAICompatibleChat(ChatOpenAI, BaseLanguageModel):
    """统一的 OpenAI 兼容对话模型。"""

    pass
