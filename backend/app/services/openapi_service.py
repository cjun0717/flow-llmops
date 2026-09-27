#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""开放 API 服务（async，迁移自 imooc openapi_service.py）。

提供基于 ApiKey 鉴权的 Chat 对话接口，支持流式（SSE）与块（一次性）两种输出。
复用阶段8的 Agent 引擎（FunctionCallAgent/ReACTAgent）+ TokenBufferMemory。
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.agents import FunctionCallAgent, ReACTAgent
from app.core.agent.entities.agent_entity import AgentConfig
from app.core.agent.entities.queue_entity import QueueEvent, queue_event_name
from app.core.language_model.entities.model_entity import ModelFeature
from app.core.memory import TokenBufferMemory
from app.entities.app_entity import AppStatus
from app.entities.conversation_entity import InvokeFrom, MessageStatus
from app.entities.dataset_entity import RetrievalSource
from app.exceptions import ForbiddenException, NotFoundException
from app.models.account import Account
from app.models.conversation import Conversation, Message
from app.models.end_user import EndUser
from app.schemas.openapi import OpenAPIChatReq
from app.schemas.response import HttpCode
from app.services.conversation_service import ConversationService


class OpenAPIService:
    """开放 API 服务"""

    @staticmethod
    async def _prepare(
        req: OpenAPIChatReq,
        account: Account,
        db: AsyncSession,
        app_service,
        app_config_service,
        language_model_service,
        retrieval_service,
        sync_redis,
    ) -> dict[str, Any]:
        """准备会话所需的全部上下文：应用/终端用户/会话/消息/Agent"""
        from app.services.app_service import AppService

        # 1.校验应用归属
        app = await AppService.get_app(req.app_id, account)

        # 2.校验应用是否已发布
        if app.status != AppStatus.PUBLISHED:
            raise NotFoundException("该应用不存在或未发布，请核实后重试")

        # 3.终端用户：传递了则校验归属，否则创建
        if req.end_user_id:
            result = await db.execute(select(EndUser).where(EndUser.id == UUID(req.end_user_id)))
            end_user = result.scalar_one_or_none()
            if not end_user or end_user.app_id != app.id:
                raise ForbiddenException("当前账号不存在或不属于该应用，请核实后重试")
        else:
            end_user = EndUser(tenant_id=account.id, app_id=app.id)
            db.add(end_user)
            await db.flush()

        # 4.会话：传递了则校验归属，否则创建
        if req.conversation_id:
            result = await db.execute(select(Conversation).where(Conversation.id == UUID(req.conversation_id)))
            conversation = result.scalar_one_or_none()
            if (
                not conversation
                or conversation.app_id != app.id
                or conversation.invoke_from != InvokeFrom.SERVICE_API
                or conversation.created_by != end_user.id
            ):
                raise ForbiddenException("该会话不存在，或者不属于该应用/终端用户/调用方式")
        else:
            conversation = Conversation(
                app_id=app.id,
                name="New Conversation",
                invoke_from=InvokeFrom.SERVICE_API,
                created_by=end_user.id,
            )
            db.add(conversation)
            await db.flush()

        # 5.获取运行时配置
        app_config = await app_config_service.get_app_config(app, db)

        # 6.新建消息记录
        message = Message(
            app_id=app.id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.SERVICE_API,
            created_by=end_user.id,
            query=req.query,
            image_urls=req.image_urls,
            status=MessageStatus.NORMAL,
        )
        db.add(message)
        await db.flush()

        # 7.加载语言模型
        llm = language_model_service.load_language_model(app_config.get("model_config", {}))

        # 8.提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=db,
            conversation=conversation,
            model_instance=llm,
        )
        history = await token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"],
        )

        # 9.工具列表
        tools = await app_config_service.get_langchain_tools_by_tools_config(app_config["tools"], db)

        # 10.知识库检索工具
        if app_config["datasets"]:
            dataset_retrieval = retrieval_service.create_langchain_tool_from_search(
                dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                account_id=account.id,
                retrieval_strategy=app_config["retrieval_config"]["retrieval_strategy"],
                k=app_config["retrieval_config"]["k"],
                score=app_config["retrieval_config"]["score"],
                retrival_source=RetrievalSource.APP,
            )
            tools.append(dataset_retrieval)

        # 11.工作流工具
        if app_config["workflows"]:
            workflow_tools = await app_config_service.get_langchain_tools_by_workflow_ids(
                [workflow["id"] for workflow in app_config["workflows"]], db
            )
            tools.extend(workflow_tools)

        # 12.根据 LLM 是否支持 tool_call 选择 Agent
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReACTAgent
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.SERVICE_API,
                preset_prompt=app_config["preset_prompt"],
                enable_long_term_memory=app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=app_config["review_config"],
            ),
            sync_redis=sync_redis,
        )

        # 13.智能体状态
        agent_state = {
            "messages": [llm.convert_to_human_message(req.query, req.image_urls)],
            "history": history,
            "long_term_memory": conversation.summary,
        }

        return {
            "app": app,
            "end_user": end_user,
            "conversation": conversation,
            "message": message,
            "app_config": app_config,
            "agent": agent,
            "agent_state": agent_state,
        }

    @staticmethod
    async def chat_stream(
        req: OpenAPIChatReq,
        account: Account,
        db: AsyncSession,
        app_service,
        app_config_service,
        language_model_service,
        retrieval_service,
        sync_redis,
    ) -> AsyncGenerator[str, None]:
        """流式 Chat 对话（SSE 事件输出）"""
        try:
            ctx = await OpenAPIService._prepare(
                req, account, db, app_service, app_config_service,
                language_model_service, retrieval_service, sync_redis,
            )
            app = ctx["app"]
            end_user = ctx["end_user"]
            conversation = ctx["conversation"]
            message = ctx["message"]
            app_config = ctx["app_config"]
            agent = ctx["agent"]
            agent_state = ctx["agent_state"]

            sync_gen = agent.stream(agent_state)
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
                                "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                                "latency": agent_thought.latency,
                            })
                    else:
                        agent_thoughts[event_id] = agent_thought

                data = {
                    **agent_thought.model_dump(include={
                        "event", "thought", "observation", "tool", "tool_input", "answer", "latency",
                    }),
                    "id": event_id,
                    "end_user_id": str(end_user.id),
                    "conversation_id": str(conversation.id),
                    "message_id": str(message.id),
                    "task_id": str(agent_thought.task_id),
                }
                yield f"event: {queue_event_name(agent_thought.event)}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n"

            # 存储消息及推理过程
            await ConversationService().save_agent_thoughts(
                account_id=account.id,
                app_id=app.id,
                app_config=app_config,
                conversation_id=conversation.id,
                message_id=message.id,
                agent_thoughts=[t for t in agent_thoughts.values()],
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
    async def chat_block(
        req: OpenAPIChatReq,
        account: Account,
        db: AsyncSession,
        app_service,
        app_config_service,
        language_model_service,
        retrieval_service,
        sync_redis,
    ) -> dict:
        """块（一次性）Chat 对话，返回完整结果字典"""
        ctx = await OpenAPIService._prepare(
            req, account, db, app_service, app_config_service,
            language_model_service, retrieval_service, sync_redis,
        )
        app = ctx["app"]
        end_user = ctx["end_user"]
        conversation = ctx["conversation"]
        message = ctx["message"]
        app_config = ctx["app_config"]
        agent = ctx["agent"]
        agent_state = ctx["agent_state"]

        # 在子线程中同步调用 agent.invoke（内部含同步 LLM/检索调用）
        loop = asyncio.get_event_loop()
        agent_result = await loop.run_in_executor(None, agent.invoke, agent_state)

        # 存储消息及推理过程
        await ConversationService().save_agent_thoughts(
            account_id=account.id,
            app_id=app.id,
            app_config=app_config,
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=agent_result.agent_thoughts,
            db=db,
        )

        return {
            "id": str(message.id),
            "end_user_id": str(end_user.id),
            "conversation_id": str(conversation.id),
            "query": req.query,
            "image_urls": req.image_urls,
            "answer": agent_result.answer,
            "total_token_count": 0,
            "latency": agent_result.latency,
            "agent_thoughts": [{
                "id": str(agent_thought.id),
                "event": agent_thought.event,
                "thought": agent_thought.thought,
                "observation": agent_thought.observation,
                "tool": agent_thought.tool,
                "tool_input": agent_thought.tool_input,
                "latency": agent_thought.latency,
                "created_at": 0,
            } for agent_thought in agent_result.agent_thoughts],
        }
