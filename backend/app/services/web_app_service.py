#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WebApp 服务（async，迁移自 imooc web_app_service.py）。

按 token 访问已发布应用：不校验归属，只要持有凭证即可对话。
会话归属当前登录账号，invoke_from=WEB_APP。
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.agents import AgentQueueManager, FunctionCallAgent, ReACTAgent
from app.core.agent.entities.agent_entity import AgentConfig
from app.core.agent.entities.queue_entity import QueueEvent, queue_event_name
from app.core.language_model.entities.model_entity import ModelFeature
from app.core.memory import TokenBufferMemory
from app.entities.app_entity import AppStatus
from app.entities.conversation_entity import InvokeFrom, MessageStatus
from app.entities.dataset_entity import RetrievalSource
from app.exceptions import ForbiddenException, NotFoundException
from app.lib.helper import datetime_to_timestamp
from app.models.account import Account
from app.models.app import App
from app.models.conversation import Conversation, Message
from app.schemas.response import HttpCode
from app.schemas.web_app import WebAppChatReq, WebAppConversationItem, WebAppInfoData, WebAppConfigData
from app.services.conversation_service import ConversationService


class WebAppService:
    """WebApp 服务"""

    @staticmethod
    async def get_web_app(token: str, db: AsyncSession) -> App:
        """根据传递的 token 获取已发布的 WebApp"""
        result = await db.execute(select(App).where(App.token == token))
        app = result.scalar_one_or_none()
        if not app or app.status != AppStatus.PUBLISHED:
            raise NotFoundException("该WebApp不存在或者未发布，请核实后重试")
        return app

    @staticmethod
    async def _model_features(model_config: dict[str, Any], db: AsyncSession) -> list[str]:
        """从用户模型记录读取特性。"""
        from app.models.user_model import UserModel

        uid = (model_config or {}).get("user_model_id") or ""
        if not uid:
            return []
        try:
            record = await db.get(UserModel, UUID(str(uid)))
        except Exception:
            return []
        return [str(f) for f in (record.features or [])] if record else []

    @staticmethod
    async def get_web_app_info(
        token: str,
        db: AsyncSession,
        app_config_service,
        language_model_service,
    ) -> WebAppInfoData:
        """根据传递的 token 获取 WebApp 基础信息"""
        app = await WebAppService.get_web_app(token, db)
        app_config = await app_config_service.get_app_config(app, db)
        features = await WebAppService._model_features(
            app_config.get("model_config") or {}, db
        )
        return WebAppInfoData(
            id=app.id,
            icon=app.icon,
            name=app.name,
            description=app.description,
            app_config=WebAppConfigData(
                opening_statement=app_config.get("opening_statement") or "",
                opening_questions=app_config.get("opening_questions") or [],
                suggested_after_answer=app_config.get("suggested_after_answer") or {},
                features=features,
                text_to_speech=app_config.get("text_to_speech") or {},
                speech_to_text=app_config.get("speech_to_text") or {},
            ),
        )

    @staticmethod
    async def web_app_chat(
        token: str,
        req: WebAppChatReq,
        account: Account,
        db: AsyncSession,
        app_config_service,
        language_model_service,
        retrieval_service,
        sync_redis,
    ) -> AsyncGenerator[str, None]:
        """根据 token+query 与指定 WebApp 对话（SSE）"""
        try:
            app = await WebAppService.get_web_app(token, db)

            if req.conversation_id:
                result = await db.execute(
                    select(Conversation).where(Conversation.id == UUID(req.conversation_id))
                )
                conversation = result.scalar_one_or_none()
                if (
                    not conversation
                    or conversation.app_id != app.id
                    or conversation.invoke_from != InvokeFrom.WEB_APP
                    or conversation.created_by != account.id
                    or conversation.is_deleted is True
                ):
                    raise ForbiddenException("该会话不存在，或者不属于当前应用/用户/调用方式")
            else:
                conversation = Conversation(
                    app_id=app.id,
                    name="New Conversation",
                    invoke_from=InvokeFrom.WEB_APP,
                    created_by=account.id,
                )
                db.add(conversation)
                await db.flush()

            app_config = await app_config_service.get_app_config(app, db)

            message = Message(
                app_id=app.id,
                conversation_id=conversation.id,
                invoke_from=InvokeFrom.WEB_APP,
                created_by=account.id,
                query=req.query,
                image_urls=req.image_urls,
                status=MessageStatus.NORMAL,
            )
            db.add(message)
            await db.flush()

            llm = language_model_service.load_language_model(app_config.get("model_config", {}))
            token_buffer_memory = TokenBufferMemory(
                db=db,
                conversation=conversation,
                model_instance=llm,
            )
            history = await token_buffer_memory.get_history_prompt_messages(
                message_limit=app_config["dialog_round"],
            )

            tools = await app_config_service.get_langchain_tools_by_tools_config(
                app_config["tools"], db
            )
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
            if app_config["workflows"]:
                workflow_tools = await app_config_service.get_langchain_tools_by_workflow_ids(
                    [workflow["id"] for workflow in app_config["workflows"]], db
                )
                tools.extend(workflow_tools)

            agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReACTAgent
            agent = agent_class(
                llm=llm,
                agent_config=AgentConfig(
                    user_id=account.id,
                    invoke_from=InvokeFrom.WEB_APP,
                    preset_prompt=app_config["preset_prompt"],
                    enable_long_term_memory=app_config["long_term_memory"]["enable"],
                    tools=tools,
                    review_config=app_config["review_config"],
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
                    else:
                        agent_thoughts[event_id] = agent_thought

                data = {
                    **agent_thought.model_dump(include={
                        "event", "thought", "observation", "tool", "tool_input", "answer",
                        "total_token_count", "total_price", "latency",
                    }),
                    "id": event_id,
                    "conversation_id": str(conversation.id),
                    "message_id": str(message.id),
                    "task_id": str(agent_thought.task_id),
                }
                yield f"event: {queue_event_name(agent_thought.event)}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n"

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
    async def stop_web_app_chat(
        token: str, task_id: UUID, account: Account, db: AsyncSession, sync_redis
    ) -> None:
        """根据 token+task_id 停止与指定 WebApp 对话"""
        await WebAppService.get_web_app(token, db)
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.WEB_APP, account.id, sync_redis)

    @staticmethod
    async def get_conversations(
        token: str, is_pinned: bool, account: Account, db: AsyncSession
    ) -> list[WebAppConversationItem]:
        """获取当前账号在该 WebApp 下的会话列表"""
        app = await WebAppService.get_web_app(token, db)
        result = await db.execute(
            select(Conversation).where(
                Conversation.app_id == app.id,
                Conversation.created_by == account.id,
                Conversation.invoke_from == InvokeFrom.WEB_APP,
                Conversation.is_pinned == is_pinned,
                Conversation.is_deleted == False,  # noqa: E712
            ).order_by(desc(Conversation.created_at))
        )
        conversations = list(result.scalars().all())
        return [
            WebAppConversationItem(
                id=item.id,
                name=item.name,
                summary=item.summary,
                created_at=datetime_to_timestamp(item.created_at),
            )
            for item in conversations
        ]
