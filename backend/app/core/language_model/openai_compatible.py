#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenAI 兼容 Chat 封装（凭证来自用户模型目录，不读 YAML）。"""
from __future__ import annotations

from typing import Any, Mapping

from langchain_core.messages import AIMessageChunk, BaseMessageChunk
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models import base as _lc_openai_base

from app.core.language_model.entities.model_entity import BaseLanguageModel

# langchain-openai 1.x 的流式解析会丢弃 DeepSeek/GLM/Qwen 等兼容接口返回的
# reasoning_content（思考内容），这里打补丁将其保留到 additional_kwargs 中，
# 便于智能体将思考过程推送为 agent_thought 事件。
_original_convert_delta_to_message_chunk = _lc_openai_base._convert_delta_to_message_chunk


def _convert_delta_to_message_chunk(
    _dict: Mapping[str, Any],
    default_class: type[BaseMessageChunk],
) -> BaseMessageChunk:
    chunk = _original_convert_delta_to_message_chunk(_dict, default_class)
    reasoning_content = _dict.get("reasoning_content") or ""
    if reasoning_content and isinstance(chunk, AIMessageChunk):
        chunk.additional_kwargs["reasoning_content"] = (
            chunk.additional_kwargs.get("reasoning_content", "") + reasoning_content
        )
    return chunk


_lc_openai_base._convert_delta_to_message_chunk = _convert_delta_to_message_chunk


class OpenAICompatibleChat(ChatOpenAI, BaseLanguageModel):
    """统一的 OpenAI 兼容对话模型。"""

    def get_num_tokens(self, text: str) -> int:
        """重写ChatOpenAI的tiktoken实现（依赖联网下载词表），使用离线估算。"""
        return BaseLanguageModel.get_num_tokens(self, text)

    def get_num_tokens_from_messages(self, messages: list, tools: Any = None) -> int:
        """重写ChatOpenAI的token统计实现。

        OpenAI 官方实现只支持官方模型名，自定义的兼容模型名（如 qwen/glm/deepseek）
        会直接抛出 NotImplementedError，导致智能体流式输出完成后无法发布统计与
        结束事件，前端一直转圈。这里统一改用离线估算。
        """
        return BaseLanguageModel.get_num_tokens_from_messages(self, messages)