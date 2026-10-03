#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI 辅助服务（async，迁移自 imooc ai_service.py）。

- optimize_prompt：SSE 流式优化预设 prompt
- generate_suggested_questions_from_message_id：根据消息生成建议问题列表
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.observability import langfuse_callbacks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from app.exceptions import ForbiddenException
from app.models.account import Account
from app.models.conversation import Message
from app.schemas.response import HttpCode
from app.services.conversation_service import ConversationService


class AIService:
    """AI 辅助服务"""

    @classmethod
    def _build_optimize_chain(cls):
        """构建优化 prompt 的 LangChain 链（同步，便于单测 mock）"""
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE),
            ("human", "{prompt}"),
        ])
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5, callbacks=langfuse_callbacks())
        return prompt_template | llm | StrOutputParser()

    @classmethod
    async def optimize_prompt(cls, prompt: str) -> AsyncGenerator[str, None]:
        """根据传递的 prompt 进行优化，SSE 流式输出"""
        try:
            optimize_chain = cls._build_optimize_chain()
            sync_gen = optimize_chain.stream({"prompt": prompt})
            loop = asyncio.get_event_loop()
            sentinel = object()

            def _next_or_none(it):
                try:
                    return next(it)
                except StopIteration:
                    return sentinel

            while True:
                chunk = await loop.run_in_executor(None, _next_or_none, sync_gen)
                if chunk is sentinel:
                    break
                data = {"optimize_prompt": chunk}
                yield f"event: optimize_prompt\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except Exception as error:
            code = getattr(error, "code", HttpCode.FAIL)
            message = getattr(error, "message", str(error))
            data = getattr(error, "data", {}) or {}
            yield "event: error\ndata:" + json.dumps({
                "code": code.value if hasattr(code, "value") else str(code),
                "message": message,
                "data": data,
            }, ensure_ascii=False) + "\n\n"

    @staticmethod
    async def generate_suggested_questions_from_message_id(
        message_id: UUID, account: Account, db: AsyncSession
    ) -> list[str]:
        """根据传递的消息id+账号生成建议问题列表"""
        result = await db.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if not message or message.created_by != account.id:
            raise ForbiddenException("该条消息不存在或无权限")

        histories = f"Human: {message.query}\nAI: {message.answer}"
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, ConversationService.generate_suggested_questions, histories
        )
