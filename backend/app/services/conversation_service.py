#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""会话服务（迁移自 imooc conversation_service.py，同步 → async）。

注意：summary/generate_conversation_name/generate_suggested_questions 为类方法，
内部使用 LangChain ChatOpenAI 同步调用（与 imooc 一致），在后台任务中执行。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.observability import langfuse_callbacks
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.entities.conversation_entity import (
    SUMMARIZER_TEMPLATE,
    CONVERSATION_NAME_TEMPLATE,
    ConversationInfo,
    SUGGESTED_QUESTIONS_TEMPLATE,
    SuggestedQuestions,
    InvokeFrom,
    MessageStatus,
)
from app.core.agent.entities.queue_entity import AgentThought, QueueEvent
from app.exceptions import NotFoundException
from app.models.account import Account
from app.models.conversation import Conversation, Message, MessageAgentThought
from app.schemas.conversation import GetConversationMessagesWithPageReq
from app.schemas.response import PageData, page_data


class ConversationService:
    """会话服务"""

    @classmethod
    def summary(cls, human_message: str, ai_message: str, old_summary: str = "") -> str:
        """根据传递的人类消息、AI消息还有原始的摘要信息总结生成一段新的摘要"""
        prompt = ChatPromptTemplate.from_template(SUMMARIZER_TEMPLATE)
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5, callbacks=langfuse_callbacks())
        summary_chain = prompt | llm | StrOutputParser()
        new_summary = summary_chain.invoke({
            "summary": old_summary,
            "new_lines": f"Human: {human_message}\nAI: {ai_message}",
        })
        return new_summary

    @classmethod
    def generate_conversation_name(cls, query: str) -> str:
        """根据传递的query生成对应的会话名字，并且语言与用户的输入保持一致"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", CONVERSATION_NAME_TEMPLATE),
            ("human", "{query}"),
        ])
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, callbacks=langfuse_callbacks())
        structured_llm = llm.with_structured_output(ConversationInfo)
        chain = prompt | structured_llm

        if len(query) > 2000:
            query = query[:300] + "...[TRUNCATED]..." + query[-300:]
        query = query.replace("\n", " ")

        conversation_info = chain.invoke({"query": query})

        name = "新的会话"
        try:
            if conversation_info and hasattr(conversation_info, "subject"):
                name = conversation_info.subject
        except Exception as e:
            logging.exception(
                "提取会话名称出错, conversation_info: %(conversation_info)s, 错误信息: %(error)s",
                {"conversation_info": conversation_info, "error": e},
            )
        if len(name) > 75:
            name = name[:75] + "..."

        return name

    @classmethod
    def generate_suggested_questions(cls, histories: str) -> list[str]:
        """根据传递的历史信息生成最多不超过3个的建议问题"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", SUGGESTED_QUESTIONS_TEMPLATE),
            ("human", "{histories}"),
        ])
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, callbacks=langfuse_callbacks())
        structured_llm = llm.with_structured_output(SuggestedQuestions)
        chain = prompt | structured_llm

        suggested_questions = chain.invoke({"histories": histories})

        questions: list[str] = []
        try:
            if suggested_questions and hasattr(suggested_questions, "questions"):
                questions = suggested_questions.questions
        except Exception as e:
            logging.exception(
                "生成建议问题出错, suggested_questions: %(suggested_questions)s, 错误信息: %(error)s",
                {"suggested_questions": suggested_questions, "error": e},
            )
        if len(questions) > 3:
            questions = questions[:3]

        return questions

    async def save_agent_thoughts(
        self,
        account_id: UUID,
        app_id: UUID,
        app_config: dict[str, Any],
        conversation_id: UUID,
        message_id: UUID,
        agent_thoughts: list[AgentThought],
        db: AsyncSession,
    ) -> None:
        """存储智能体推理步骤消息"""
        # 1.定义变量存储推理位置及总耗时
        position = 0
        latency = 0

        # 2.重新查询conversation以及message
        conversation = await self.get_conversation_by_id(conversation_id, db)
        message = await self.get_message_by_id(message_id, db)

        # 3.循环遍历所有的智能体推理过程执行存储操作
        for agent_thought in agent_thoughts:
            # 4.存储长期记忆召回、推理、消息、动作、知识库检索等步骤
            if agent_thought.event in [
                QueueEvent.LONG_TERM_MEMORY_RECALL,
                QueueEvent.AGENT_THOUGHT,
                QueueEvent.AGENT_MESSAGE,
                QueueEvent.AGENT_ACTION,
                QueueEvent.DATASET_RETRIEVAL,
            ]:
                # 5.更新位置及总耗时
                position += 1
                latency += agent_thought.latency

                # 6.创建智能体消息推理步骤
                db.add(MessageAgentThought(
                    app_id=app_id,
                    conversation_id=conversation.id,
                    message_id=message.id,
                    invoke_from=InvokeFrom.DEBUGGER,
                    created_by=account_id,
                    position=position,
                    event=agent_thought.event,
                    thought=agent_thought.thought,
                    observation=agent_thought.observation,
                    tool=agent_thought.tool,
                    tool_input=agent_thought.tool_input,
                    # 消息相关数据
                    message=agent_thought.message,
                    message_token_count=agent_thought.message_token_count,
                    message_unit_price=agent_thought.message_unit_price,
                    message_price_unit=agent_thought.message_price_unit,
                    # 答案相关字段
                    answer=agent_thought.answer,
                    answer_token_count=agent_thought.answer_token_count,
                    answer_unit_price=agent_thought.answer_unit_price,
                    answer_price_unit=agent_thought.answer_price_unit,
                    # Agent推理统计相关
                    total_token_count=agent_thought.total_token_count,
                    total_price=agent_thought.total_price,
                    latency=agent_thought.latency,
                ))

            # 7.检测事件是否为Agent_message
            if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                # 8.更新消息信息
                message.message = agent_thought.message
                message.message_token_count = agent_thought.message_token_count
                message.message_unit_price = agent_thought.message_unit_price
                message.message_price_unit = agent_thought.message_price_unit
                # 答案相关字段
                message.answer = agent_thought.answer
                message.answer_token_count = agent_thought.answer_token_count
                message.answer_unit_price = agent_thought.answer_unit_price
                message.answer_price_unit = agent_thought.answer_price_unit
                # Agent推理统计相关
                message.total_token_count = agent_thought.total_token_count
                message.total_price = agent_thought.total_price
                message.latency = latency

                # 9.检测是否开启长期记忆，开启则在后台生成摘要
                if app_config["long_term_memory"]["enable"]:
                    self._generate_summary_and_update_background(
                        conversation_id=conversation.id,
                        query=message.query,
                        answer=agent_thought.answer,
                    )

                # 10.处理生成新会话名称（仅当会话为新会话时）
                if await self._is_conversation_new(conversation.id, db):
                    self._generate_conversation_name_and_update_background(
                        conversation_id=conversation.id,
                        query=message.query,
                    )

            # 11.判断是否为停止或者错误，如果是则需要更新消息状态
            if agent_thought.event in [QueueEvent.TIMEOUT, QueueEvent.STOP, QueueEvent.ERROR]:
                message.status = agent_thought.event
                message.error = agent_thought.observation
                break

        await db.commit()

    @staticmethod
    def _generate_summary_and_update_background(
        conversation_id: UUID, query: str, answer: str
    ) -> None:
        """在后台任务中生成会话摘要并更新"""
        import asyncio
        from app.db import AsyncSessionLocal

        async def _run() -> None:
            try:
                async with AsyncSessionLocal() as inner_db:
                    result = await inner_db.execute(
                        select(Conversation).where(Conversation.id == conversation_id)
                    )
                    conversation = result.scalar_one_or_none()
                    if conversation is None:
                        return
                    new_summary = ConversationService.summary(query, answer, conversation.summary)
                    conversation.summary = new_summary
                    await inner_db.commit()
            except Exception:
                logging.exception("后台生成会话摘要出错, conversation_id: %s", conversation_id)

        try:
            asyncio.create_task(_run())
        except RuntimeError:
            # 无运行事件循环，跳过
            pass

    @staticmethod
    def _generate_conversation_name_and_update_background(
        conversation_id: UUID, query: str
    ) -> None:
        """在后台任务中生成会话名字并更新"""
        import asyncio
        from app.db import AsyncSessionLocal

        async def _run() -> None:
            try:
                async with AsyncSessionLocal() as inner_db:
                    result = await inner_db.execute(
                        select(Conversation).where(Conversation.id == conversation_id)
                    )
                    conversation = result.scalar_one_or_none()
                    if conversation is None:
                        return
                    new_name = ConversationService.generate_conversation_name(query)
                    conversation.name = new_name
                    await inner_db.commit()
            except Exception:
                logging.exception("后台生成会话名称出错, conversation_id: %s", conversation_id)

        try:
            asyncio.create_task(_run())
        except RuntimeError:
            pass

    @staticmethod
    async def _is_conversation_new(conversation_id: UUID, db: AsyncSession) -> bool:
        """判断该会话是否是第一次创建（消息数<=1）"""
        result = await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        )
        message_count = result.scalar() or 0
        return message_count <= 1

    @staticmethod
    async def get_conversation_by_id(conversation_id: UUID, db: AsyncSession) -> Conversation:
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundException("该会话不存在，请核实后重试")
        return conversation

    @staticmethod
    async def get_message_by_id(message_id: UUID, db: AsyncSession) -> Message:
        result = await db.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if message is None:
            raise NotFoundException("该消息不存在，请核实后重试")
        return message

    @staticmethod
    async def get_conversation(conversation_id: UUID, account: Account, db: AsyncSession) -> Conversation:
        """根据传递的会话id+account，获取指定的会话信息"""
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = result.scalar_one_or_none()
        if (
            not conversation
            or conversation.created_by != account.id
            or conversation.is_deleted
        ):
            raise NotFoundException("该会话不存在或被删除，请核实后重试")
        return conversation

    @staticmethod
    async def get_message(message_id: UUID, account: Account, db: AsyncSession) -> Message:
        """根据传递的消息id+账号，获取指定的消息"""
        result = await db.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if (
            not message
            or message.created_by != account.id
            or message.is_deleted
        ):
            raise NotFoundException("该消息不存在或被删除，请核实后重试")
        return message

    @staticmethod
    async def get_conversation_messages_with_page(
        conversation_id: UUID,
        req: GetConversationMessagesWithPageReq,
        account: Account,
        db: AsyncSession,
    ) -> PageData:
        """根据传递的会话id+请求数据，获取当前账号下该会话的消息分页列表数据"""
        # 1.获取会话并校验权限
        conversation = await ConversationService.get_conversation(conversation_id, account, db)

        # 2.构建游标条件
        filters = [
            Message.conversation_id == conversation.id,
            Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
            Message.answer != "",
            Message.is_deleted == False,  # noqa: E712
        ]
        if req.created_at:
            created_at_datetime = datetime.fromtimestamp(req.created_at)
            filters.append(Message.created_at <= created_at_datetime)

        # 3.统计总数
        count_result = await db.execute(
            select(func.count()).select_from(Message).where(*filters)
        )
        total_record = count_result.scalar() or 0

        # 4.查询分页数据
        result = await db.execute(
            select(Message).options(selectinload(Message.agent_thoughts)).where(*filters)
            .order_by(desc(Message.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        messages = list(result.scalars().all())

        from app.schemas.conversation import MessageItem
        items = [MessageItem.from_model(m) for m in messages]
        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @staticmethod
    async def delete_conversation(conversation_id: UUID, account: Account, db: AsyncSession) -> Conversation:
        """根据传递的会话id+账号删除指定的会话记录"""
        conversation = await ConversationService.get_conversation(conversation_id, account, db)
        conversation.is_deleted = True
        await db.commit()
        return conversation

    @staticmethod
    async def delete_message(
        conversation_id: UUID, message_id: UUID, account: Account, db: AsyncSession
    ) -> Message:
        """根据传递的会话id+消息id删除指定的消息记录"""
        conversation = await ConversationService.get_conversation(conversation_id, account, db)
        message = await ConversationService.get_message(message_id, account, db)
        if conversation.id != message.conversation_id:
            raise NotFoundException("该会话下不存在该消息，请核实后重试")
        message.is_deleted = True
        await db.commit()
        return message

    @staticmethod
    async def update_conversation(
        conversation_id: UUID, account: Account, db: AsyncSession, **kwargs
    ) -> Conversation:
        """根据传递的会话id+账号+kwargs更新会话信息"""
        conversation = await ConversationService.get_conversation(conversation_id, account, db)
        for key, value in kwargs.items():
            setattr(conversation, key, value)
        await db.commit()
        return conversation
