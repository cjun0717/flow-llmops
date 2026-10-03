#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""微信公众号服务（async，迁移自 imooc wechat_service.py）。

GET：校验 signature 后原样返回 echostr。
POST：仅处理文本；先落库再后台跑 Agent，立刻回复「思考中，请回复“1”获取结果。」（微信 5s 超时）。
"""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.agents import FunctionCallAgent, ReACTAgent
from app.core.agent.entities.agent_entity import AgentConfig
from app.core.language_model.entities.model_entity import ModelFeature
from app.core.memory import TokenBufferMemory
from app.db import AsyncSessionLocal
from app.entities.app_entity import AppStatus
from app.entities.conversation_entity import InvokeFrom, MessageStatus
from app.entities.dataset_entity import RetrievalSource
from app.entities.platform_entity import WechatConfigStatus
from app.exceptions import FailException
from app.lib.wechat import (
    WechatInboundMessage,
    check_wechat_signature,
    parse_wechat_message,
    render_text_reply,
)
from app.models.app import App
from app.models.conversation import Conversation, Message
from app.models.end_user import EndUser
from app.models.platform import WechatConfig, WechatEndUser, WechatMessage
from app.services.conversation_service import ConversationService
from app.services.platform_service import PlatformService

logger = logging.getLogger(__name__)

_XML_MEDIA_TYPE = "application/xml; charset=utf-8"


class WechatService:
    """微信公众号校验与消息推送"""

    @staticmethod
    def _xml_response(message: WechatInboundMessage | None, content: str) -> Response:
        return Response(
            content=render_text_reply(message, content),
            media_type=_XML_MEDIA_TYPE,
        )

    @staticmethod
    async def _load_published_app(app_id: UUID, db: AsyncSession) -> tuple[App | None, WechatConfig | None]:
        result = await db.execute(select(App).where(App.id == app_id))
        app = result.scalar_one_or_none()
        if not app or app.status != AppStatus.PUBLISHED:
            return None, None
        result = await db.execute(select(WechatConfig).where(WechatConfig.app_id == app.id))
        config = result.scalar_one_or_none()
        if config:
            synced = PlatformService.compute_wechat_status(
                app.status, config.wechat_app_id, config.wechat_app_secret, config.wechat_token
            )
            if config.status != synced:
                config.status = synced
                await db.commit()
                await db.refresh(config)
        return app, config

    @classmethod
    async def handle(
        cls,
        app_id: UUID,
        request: Request,
        db: AsyncSession,
        app_config_service,
        language_model_service,
        retrieval_service,
        sync_redis,
    ) -> Response:
        """微信公众号 API 校验与消息推送"""
        inbound = parse_wechat_message(await request.body()) if request.method == "POST" else None
        app, wechat_config = await cls._load_published_app(app_id, db)

        if app is None:
            if request.method == "GET":
                raise FailException("该应用未发布或不存在，无法使用，请核实后重试")
            return cls._xml_response(inbound, "该应用未发布或不存在，无法使用，请核实后重试")

        if wechat_config is None or wechat_config.status != WechatConfigStatus.CONFIGURED:
            if request.method == "GET":
                raise FailException("该应用未发布到微信公众号，无法使用，请核实后重试")
            return cls._xml_response(inbound, "该应用未发布到微信公众号，无法使用，请核实后重试")

        if request.method == "GET":
            signature = request.query_params.get("signature") or ""
            timestamp = request.query_params.get("timestamp") or ""
            nonce = request.query_params.get("nonce") or ""
            echostr = request.query_params.get("echostr") or ""
            if not check_wechat_signature(wechat_config.wechat_token or "", signature, timestamp, nonce):
                raise FailException("微信公众号服务器配置接入失败")
            return PlainTextResponse(echostr)

        return await cls._handle_post(
            app, wechat_config, inbound, db,
            app_config_service, language_model_service, retrieval_service, sync_redis,
        )

    @classmethod
    async def _get_or_create_wechat_end_user(
        cls, app: App, openid: str, db: AsyncSession
    ) -> WechatEndUser:
        result = await db.execute(
            select(WechatEndUser).where(
                WechatEndUser.openid == openid,
                WechatEndUser.app_id == app.id,
            )
        )
        wechat_end_user = result.scalar_one_or_none()
        if wechat_end_user:
            return wechat_end_user

        end_user = EndUser(tenant_id=app.account_id, app_id=app.id)
        db.add(end_user)
        await db.flush()
        wechat_end_user = WechatEndUser(
            openid=openid,
            app_id=app.id,
            end_user_id=end_user.id,
        )
        db.add(wechat_end_user)
        await db.flush()
        return wechat_end_user

    @classmethod
    async def _get_or_create_conversation(
        cls, wechat_end_user: WechatEndUser, db: AsyncSession
    ) -> Conversation:
        result = await db.execute(
            select(Conversation).where(
                Conversation.created_by == wechat_end_user.end_user_id,
                Conversation.app_id == wechat_end_user.app_id,
                Conversation.invoke_from == InvokeFrom.SERVICE_API,
                Conversation.is_deleted == False,  # noqa: E712
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            return conversation
        conversation = Conversation(
            app_id=wechat_end_user.app_id,
            name="New Conversation",
            invoke_from=InvokeFrom.SERVICE_API,
            created_by=wechat_end_user.end_user_id,
        )
        db.add(conversation)
        await db.flush()
        return conversation

    @classmethod
    async def _try_push_pending(
        cls,
        wechat_end_user: WechatEndUser,
        inbound: WechatInboundMessage,
        db: AsyncSession,
    ) -> Response | None:
        """用户回复 1 时尝试推送最近一条未推送的 Agent 结果。"""
        result = await db.execute(
            select(WechatMessage)
            .where(WechatMessage.wechat_end_user_id == wechat_end_user.id)
            .order_by(desc(WechatMessage.created_at))
        )
        wechat_message = result.scalars().first()
        if not wechat_message or wechat_message.is_pushed:
            return None

        result = await db.execute(select(Message).where(Message.id == wechat_message.message_id))
        message = result.scalar_one_or_none()
        if not message:
            return None

        if message.status in (MessageStatus.NORMAL, MessageStatus.STOP):
            if message.answer.strip() != "":
                wechat_message.is_pushed = True
                await db.commit()
                return cls._xml_response(inbound, message.answer.strip())
            return cls._xml_response(inbound, "该Agent智能体任务正在处理中，请稍后重新回复`1`获取结果。")
        if message.status == MessageStatus.TIMEOUT:
            return cls._xml_response(inbound, "该Agent智能体处理任务超时，请重新发起提问。")
        if message.status == MessageStatus.ERROR:
            return cls._xml_response(inbound, f"该Agent智能体处理任务出错，请重新发起提问，错误信息: {message.error}。")
        return None

    @classmethod
    async def _handle_post(
        cls,
        app: App,
        _wechat_config: WechatConfig,
        inbound: WechatInboundMessage | None,
        db: AsyncSession,
        app_config_service,
        language_model_service,
        retrieval_service,
        sync_redis,
    ) -> Response:
        if inbound is None or inbound.msg_type != "text":
            return cls._xml_response(inbound, "抱歉，该Agent目前暂时只支持文本消息。")

        content = inbound.content or ""
        openid = inbound.source
        wechat_end_user = await cls._get_or_create_wechat_end_user(app, openid, db)

        if content.strip() == "1":
            pushed = await cls._try_push_pending(wechat_end_user, inbound, db)
            if pushed is not None:
                return pushed

        app_config = await app_config_service.get_app_config(app, db)
        conversation = await cls._get_or_create_conversation(wechat_end_user, db)
        message = Message(
            app_id=app.id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.SERVICE_API,
            created_by=wechat_end_user.end_user_id,
            query=content,
            image_urls=[],
            status=MessageStatus.NORMAL,
        )
        db.add(message)
        await db.flush()
        db.add(WechatMessage(
            wechat_end_user_id=wechat_end_user.id,
            message_id=message.id,
            is_pushed=False,
        ))
        await db.commit()

        asyncio.create_task(
            cls.background_chat(
                app_id=app.id,
                conversation_id=conversation.id,
                message_id=message.id,
                query=content,
                app_config_service=app_config_service,
                language_model_service=language_model_service,
                retrieval_service=retrieval_service,
                sync_redis=sync_redis,
            )
        )
        return cls._xml_response(inbound, "思考中，请回复“1”获取结果。")

    @classmethod
    async def background_chat(
        cls,
        *,
        app_id: UUID,
        conversation_id: UUID,
        message_id: UUID,
        query: str,
        app_config_service,
        language_model_service,
        retrieval_service,
        sync_redis,
    ) -> None:
        """后台跑 Agent，避免超过微信 5s 响应窗口。"""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(App).where(App.id == app_id))
                app = result.scalar_one_or_none()
                result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
                conversation = result.scalar_one_or_none()
                if not app or not conversation:
                    return

                app_config = await app_config_service.get_app_config(app, db)
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
                    tools.append(
                        retrieval_service.create_langchain_tool_from_search(
                            dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                            account_id=app.account_id,
                            retrieval_strategy=app_config["retrieval_config"]["retrieval_strategy"],
                            k=app_config["retrieval_config"]["k"],
                            score=app_config["retrieval_config"]["score"],
                            retrival_source=RetrievalSource.APP,
                        )
                    )
                if app_config["workflows"]:
                    tools.extend(
                        await app_config_service.get_langchain_tools_by_workflow_ids(
                            [workflow["id"] for workflow in app_config["workflows"]], db
                        )
                    )

                agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReACTAgent
                agent = agent_class(
                    llm=llm,
                    agent_config=AgentConfig(
                        user_id=app.account_id,
                        invoke_from=InvokeFrom.SERVICE_API,
                        preset_prompt=app_config["preset_prompt"],
                        enable_long_term_memory=app_config["long_term_memory"]["enable"],
                        tools=tools,
                        review_config=app_config["review_config"],
                    ),
                    sync_redis=sync_redis,
                )
                agent_state = {
                    "messages": [llm.convert_to_human_message(query, [])],
                    "history": history,
                    "long_term_memory": conversation.summary,
                }
                agent_result = await asyncio.to_thread(agent.invoke, agent_state)
                await ConversationService().save_agent_thoughts(
                    account_id=app.account_id,
                    app_id=app.id,
                    app_config=app_config,
                    conversation_id=conversation.id,
                    message_id=message_id,
                    agent_thoughts=list(agent_result.agent_thoughts or []),
                    db=db,
                )
                await db.commit()
        except Exception as error:
            logger.error("微信 Agent 后台任务失败: %s", error, exc_info=True)
            try:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(Message).where(Message.id == message_id))
                    message = result.scalar_one_or_none()
                    if message:
                        message.status = MessageStatus.ERROR
                        message.error = str(error)
                        await db.commit()
            except Exception:
                logger.exception("回写微信消息错误状态失败")
