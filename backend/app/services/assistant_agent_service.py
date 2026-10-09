#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""辅助智能体服务（async，迁移自 imooc assistant_agent_service.py）。"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.agent.agents import AgentQueueManager, FunctionCallAgent
from app.core.agent.entities.agent_entity import AgentConfig
from app.core.agent.entities.queue_entity import QueueEvent, queue_event_name
from app.core.memory import TokenBufferMemory
from app.entities.conversation_entity import InvokeFrom, MessageStatus
from app.models.account import Account
from app.models.conversation import Conversation, Message
from app.schemas.assistant_agent import AssistantAgentChatReq, GetAssistantAgentMessagesWithPageReq
from app.schemas.conversation import MessageItem
from app.schemas.response import HttpCode, PageData, page_data
from app.services.conversation_service import ConversationService
from app.services.assistant_knowledge_service import AssistantKnowledgeService


class AssistantAgentService:
    """辅助智能体服务"""

    @staticmethod
    async def _get_or_create_assistant_conversation(
        account: Account, db: AsyncSession
    ) -> Conversation:
        """获取或创建当前账号的辅助 Agent 会话"""
        conversation = None
        if account.assistant_agent_conversation_id is not None:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == account.assistant_agent_conversation_id,
                    Conversation.invoke_from == InvokeFrom.ASSISTANT_AGENT,
                )
            )
            conversation = result.scalar_one_or_none()

        if not account.assistant_agent_conversation_id or not conversation:
            conversation = Conversation(
                app_id=settings.ASSISTANT_AGENT_ID,
                name="New Conversation",
                invoke_from=InvokeFrom.ASSISTANT_AGENT,
                created_by=account.id,
            )
            db.add(conversation)
            await db.flush()
            account.assistant_agent_conversation_id = conversation.id
            await db.commit()
            await db.refresh(account)

        return conversation

    @staticmethod
    def load_assistant_agent_llm(language_model_service, account_id=None):
        """加载当前账号的默认对话模型。"""
        from app.db import SyncSessionLocal
        from app.exceptions import FailException
        from app.models.user_model import UserModelType
        from app.services.user_model_service import (
            UserModelService,
            build_chat_model,
            sanitize_chat_parameters,
        )

        if account_id is None:
            raise FailException("请先在模型管理中添加对话模型")
        with SyncSessionLocal() as db:
            record = UserModelService.get_default_sync(account_id, UserModelType.CHAT, db)
            if record is None:
                raise FailException("请先在模型管理中添加对话模型")
            parameters = sanitize_chat_parameters({
                "temperature": settings.ASSISTANT_AGENT_TEMPERATURE,
                "max_tokens": settings.ASSISTANT_AGENT_MAX_TOKENS,
            })
            return build_chat_model(record, parameters)

    @staticmethod
    async def chat(
        req: AssistantAgentChatReq,
        account: Account,
        db: AsyncSession,
        language_model_service,
        knowledge_service: AssistantKnowledgeService,
        sync_redis,
    ) -> AsyncGenerator[str, None]:
        """传递 query 与账号实现与辅助 Agent 进行会话（SSE 流式）"""
        try:
            assistant_agent_id = settings.ASSISTANT_AGENT_ID
            conversation = await AssistantAgentService._get_or_create_assistant_conversation(
                account, db
            )

            message = Message(
                app_id=assistant_agent_id,
                conversation_id=conversation.id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT,
                created_by=account.id,
                query=req.query,
                image_urls=req.image_urls,
                status=MessageStatus.NORMAL,
            )
            db.add(message)
            await db.flush()

            llm = AssistantAgentService.load_assistant_agent_llm(
                language_model_service, account.id
            )

            token_buffer_memory = TokenBufferMemory(
                db=db,
                conversation=conversation,
                model_instance=llm,
            )
            history = await token_buffer_memory.get_history_prompt_messages(message_limit=3)

            tools = [
                knowledge_service.convert_to_tool(account.id),
                AssistantAgentService.convert_create_app_to_tool(account.id),
            ]

            agent = FunctionCallAgent(
                llm=llm,
                agent_config=AgentConfig(
                    user_id=account.id,
                    invoke_from=InvokeFrom.ASSISTANT_AGENT,
                    enable_long_term_memory=True,
                    tools=tools,
                ),
                sync_redis=sync_redis,
            )

            sync_gen = agent.stream({
                "messages": [llm.convert_to_human_message(req.query, req.image_urls)],
                "history": history,
                "long_term_memory": conversation.summary,
            })

            agent_thoughts: dict = {}
            loop = asyncio.get_event_loop()
            sentinel = object()

            def _next_or_none(it):
                try:
                    return next(it)
                except StopIteration:
                    return sentinel

            while True:
                agent_thought = await loop.run_in_executor(None, _next_or_none, sync_gen)
                if agent_thought is sentinel:
                    break

                event_id = str(agent_thought.id)

                if agent_thought.event != QueueEvent.PING:
                    if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                        if event_id not in agent_thoughts:
                            agent_thoughts[event_id] = agent_thought
                        else:
                            agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                                "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                                "message": agent_thought.message,
                                "message_token_count": agent_thought.message_token_count,
                                "message_unit_price": agent_thought.message_unit_price,
                                "message_price_unit": agent_thought.message_price_unit,
                                "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                                "answer_token_count": agent_thought.answer_token_count,
                                "answer_unit_price": agent_thought.answer_unit_price,
                                "answer_price_unit": agent_thought.answer_price_unit,
                                "total_token_count": agent_thought.total_token_count,
                                "total_price": agent_thought.total_price,
                                "latency": agent_thought.latency,
                            })
                    elif agent_thought.event == QueueEvent.AGENT_THOUGHT:
                        # 思考模型流式输出的思考内容按id叠加，便于完整存储
                        if event_id not in agent_thoughts:
                            agent_thoughts[event_id] = agent_thought
                        else:
                            agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                                "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                                "latency": agent_thought.latency,
                            })
                    else:
                        agent_thoughts[event_id] = agent_thought

                data = {
                    **agent_thought.model_dump(include={
                        "event", "thought", "observation", "tool", "tool_input", "answer",
                        "latency", "total_token_count",
                    }),
                    "id": event_id,
                    "conversation_id": str(conversation.id),
                    "message_id": str(message.id),
                    "task_id": str(agent_thought.task_id),
                }
                yield f"event: {queue_event_name(agent_thought.event)}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n"

            await ConversationService().save_agent_thoughts(
                account_id=account.id,
                app_id=assistant_agent_id,
                app_config={"long_term_memory": {"enable": True}},
                conversation_id=conversation.id,
                message_id=message.id,
                agent_thoughts=[agent_thought for agent_thought in agent_thoughts.values()],
                db=db,
            )
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
    def stop_chat(task_id: UUID, account: Account, sync_redis) -> None:
        """根据传递的任务id+账号停止某次响应会话"""
        AgentQueueManager.set_stop_flag(
            task_id, InvokeFrom.ASSISTANT_AGENT, account.id, sync_redis
        )

    @staticmethod
    async def get_conversation_messages_with_page(
        req: GetAssistantAgentMessagesWithPageReq,
        account: Account,
        db: AsyncSession,
    ) -> PageData:
        """根据传递的请求+账号获取与辅助 Agent 对话的消息分页列表"""
        conversation = await AssistantAgentService._get_or_create_assistant_conversation(
            account, db
        )

        filters = [
            Message.conversation_id == conversation.id,
            Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
            Message.answer != "",
            Message.is_deleted == False,  # noqa: E712
        ]
        if req.created_at:
            created_at_datetime = datetime.fromtimestamp(req.created_at)
            filters.append(Message.created_at <= created_at_datetime)

        count_result = await db.execute(
            select(func.count()).select_from(Message).where(*filters)
        )
        total_record = count_result.scalar() or 0

        result = await db.execute(
            select(Message).options(selectinload(Message.agent_thoughts)).where(*filters)
            .order_by(desc(Message.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        messages = list(result.scalars().all())
        items = [MessageItem.from_model(m) for m in messages]
        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @staticmethod
    async def delete_conversation(account: Account, db: AsyncSession) -> None:
        """根据传递的账号，清空辅助 Agent 智能体会话消息列表"""
        account.assistant_agent_conversation_id = None
        await db.commit()

    @classmethod
    def convert_create_app_to_tool(cls, account_id: UUID) -> BaseTool:
        """定义自动创建 Agent 应用 LangChain 工具"""

        class CreateAppInput(BaseModel):
            """创建Agent/应用输入结构"""
            name: str = Field(description="需要创建的Agent/应用名称，长度不超过50个字符")
            description: str = Field(description="需要创建的Agent/应用描述，请详细概括该应用的功能")

        @tool("create_app", args_schema=CreateAppInput)
        def create_app(name: str, description: str) -> str:
            """如果用户提出了需要创建一个Agent/应用，你可以调用此工具，参数的输入是应用的名称+描述，返回的数据是创建后的成功提示"""
            from app.tasks.app_task import auto_create_app

            auto_create_app.delay(name, description, str(account_id))
            return f"已调用后端异步任务创建Agent应用。\n应用名称: {name}\n应用描述: {description}"

        return create_app
