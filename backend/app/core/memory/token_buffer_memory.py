#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""基于token计数的缓冲记忆组件（迁移自 imooc token_buffer_memory.py，同步 → async）。

注意：trim_messages 为同步函数且需调用 model_instance 的 get_num_tokens，
在 async 上下文中通过 run_in_threadpool 包装同步调用。
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from langchain_core.messages import AnyMessage, AIMessage, trim_messages, get_buffer_string
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.language_model.entities.model_entity import BaseLanguageModel
from app.entities.conversation_entity import MessageStatus
from app.models.conversation import Conversation, Message


@dataclass
class TokenBufferMemory:
    """基于token计数的缓冲记忆组件"""
    db: AsyncSession  # 数据库会话
    conversation: Conversation  # 会话模型
    model_instance: BaseLanguageModel  # LLM大语言模型

    async def get_history_prompt_messages(
        self,
        max_token_limit: int = 2000,
        message_limit: int = 10,
    ) -> list[AnyMessage]:
        """根据传递的token限制+消息条数限制获取指定会话模型的历史消息列表"""
        # 1.判断会话模型是否存在，如果不存在则直接返回空列表
        if self.conversation is None:
            return []

        # 2.查询该会话的消息列表，并且使用时间进行倒序，同时匹配答案不为空、匹配会话id、没有软删除、状态是正常
        conversation_id: UUID = self.conversation.id
        result = await self.db.execute(
            select(Message).filter(
                Message.conversation_id == conversation_id,
                Message.answer != "",
                Message.is_deleted == False,  # noqa: E712
                Message.status.in_([MessageStatus.NORMAL, MessageStatus.STOP, MessageStatus.TIMEOUT]),
            ).order_by(desc(Message.created_at)).limit(message_limit)
        )
        messages = list(reversed(result.scalars().all()))

        # 3.将messages转换成LangChain消息列表
        prompt_messages: list[AnyMessage] = []
        for message in messages:
            prompt_messages.extend([
                self.model_instance.convert_to_human_message(message.query, message.image_urls),
                AIMessage(content=message.answer),
            ])

        # 4.调用LangChain继承的trim_messages函数剪切消息列表（同步调用，用 threadpool 包装）
        return await run_in_threadpool(
            trim_messages,
            messages=prompt_messages,
            max_tokens=max_token_limit,
            token_counter=self.model_instance,
            strategy="last",
            start_on="human",
            end_on="ai",
        )

    async def get_history_prompt_text(
        self,
        human_prefix: str = "Human",
        ai_prefix: str = "AI",
        max_token_limit: int = 2000,
        message_limit: int = 10,
    ) -> str:
        """根据传递的数据获取指定会话历史消息提示文本(短期记忆的文本形式，用于文本生成模型)"""
        # 1.根据传递的信息获取历史消息列表
        messages = await self.get_history_prompt_messages(max_token_limit, message_limit)

        # 2.调用LangChain集成的get_buffer_string()函数将消息列表转换成文本
        return get_buffer_string(messages, human_prefix, ai_prefix)
