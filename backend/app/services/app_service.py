#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用服务（CRUD 部分）。"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from copy import deepcopy
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.agent.entities.agent_entity import AgentConfig
from app.core.agent.entities.queue_entity import QueueEvent, queue_event_name
from app.core.agent.agents import FunctionCallAgent, ReACTAgent
from app.core.language_model.entities.model_entity import ModelFeature
from app.core.memory import TokenBufferMemory
from app.entities.app_entity import (
    AppStatus,
    AppConfigType,
    DEFAULT_APP_CONFIG,
    GENERATE_ICON_PROMPT_TEMPLATE,
)
from app.entities.conversation_entity import InvokeFrom, MessageStatus
from app.entities.dataset_entity import RetrievalSource
from app.exceptions import FailException, ForbiddenException, NotFoundException, ValidateException
from app.lib.helper import generate_random_string
from app.models.account import Account
from app.models.app import App, AppConfig, AppConfigVersion, AppDatasetJoin
from app.models.api_tool import ApiTool
from app.models.conversation import Conversation, Message
from app.models.mcp_tool import McpTool
from app.models.user_model import UserModel
from app.schemas.app import (
    AppDetailData,
    AppListItemData,
    CreateAppReq,
    GetAppsWithPageReq,
    GetPublishHistoriesWithPageReq,
    PublishHistoryItem,
    UpdateAppReq,
)
from app.schemas.conversation import (
    DebugChatReq,
    GetDebugConversationMessagesWithPageReq,
    MessageItem,
)
from app.schemas.response import HttpCode, PageData, page_data
from app.services.conversation_service import ConversationService


class AppService:
    """应用 CRUD"""

    @staticmethod
    async def _get_draft_config(app_id: UUID, db: AsyncSession) -> AppConfigVersion:
        """获取应用的草稿配置（替代原始 @property 查库逻辑）"""
        result = await db.execute(
            select(AppConfigVersion).where(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.DRAFT,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_or_create_draft_config(
        app_id: UUID, db: AsyncSession
    ) -> AppConfigVersion:
        """获取草稿配置，不存在则创建默认配置"""
        config = await AppService._get_draft_config(app_id, db)
        if config is not None:
            return config
        config = AppConfigVersion(
            app_id=app_id,
            version=0,
            config_type=AppConfigType.DRAFT,
            **DEFAULT_APP_CONFIG,
        )
        db.add(config)
        await db.flush()
        return config

    @staticmethod
    async def _model_display_name(model_config: dict | None, db: AsyncSession) -> str:
        uid = (model_config or {}).get("user_model_id") or ""
        if not uid:
            return "未选择模型"
        try:
            record = await db.get(UserModel, UUID(str(uid)))
        except Exception:
            return "未选择模型"
        return record.name if record else "未选择模型"

    @staticmethod
    async def get_app(app_id: UUID, account: Account, db: AsyncSession) -> App:
        """获取应用并校验权限"""
        result = await db.execute(select(App).where(App.id == app_id))
        app = result.scalar_one_or_none()
        if not app:
            raise NotFoundException("该应用不存在，请核实后重试")
        if app.account_id != account.id:
            raise ForbiddenException("当前账号无权限访问该应用，请核实后尝试")
        return app

    @staticmethod
    async def create_app(
        req: CreateAppReq, account: Account, db: AsyncSession
    ) -> App:
        """创建应用 + 草稿配置"""
        app = App(
            account_id=account.id,
            name=req.name,
            icon=req.icon,
            description=req.description,
            status=AppStatus.DRAFT,
        )
        db.add(app)
        await db.flush()

        config_data = deepcopy(DEFAULT_APP_CONFIG)
        from app.services.user_model_service import UserModelService
        config_data["model_config"] = await UserModelService.default_chat_model_config(
            account, db
        )
        config = AppConfigVersion(
            app_id=app.id,
            version=0,
            config_type=AppConfigType.DRAFT,
            **config_data,
        )
        db.add(config)
        await db.flush()

        app.draft_app_config_id = config.id
        await db.commit()
        await db.refresh(app)
        return app

    @staticmethod
    async def update_app(
        app_id: UUID, req: UpdateAppReq, account: Account, db: AsyncSession
    ) -> None:
        """修改应用基础信息"""
        app = await AppService.get_app(app_id, account, db)
        app.name = req.name
        app.icon = req.icon
        app.description = req.description
        await db.commit()

    @staticmethod
    async def delete_app(app_id: UUID, account: Account, db: AsyncSession) -> None:
        """删除应用"""
        app = await AppService.get_app(app_id, account, db)
        await db.delete(app)
        await db.commit()

    @staticmethod
    async def copy_app(app_id: UUID, account: Account, db: AsyncSession) -> App:
        """复制应用 + 草稿配置"""
        app = await AppService.get_app(app_id, account, db)
        draft_config = await AppService._get_or_create_draft_config(app_id, db)

        new_app = App(
            account_id=app.account_id,
            name=app.name,
            icon=app.icon,
            description=app.description,
            status=AppStatus.DRAFT,
        )
        db.add(new_app)
        await db.flush()

        new_config = AppConfigVersion(
            app_id=new_app.id,
            version=0,
            config_type=AppConfigType.DRAFT,
            model_config=draft_config.model_config,
            dialog_round=draft_config.dialog_round,
            preset_prompt=draft_config.preset_prompt,
            tools=draft_config.tools,
            workflows=draft_config.workflows,
            datasets=draft_config.datasets,
            retrieval_config=draft_config.retrieval_config,
            long_term_memory=draft_config.long_term_memory,
            opening_statement=draft_config.opening_statement,
            opening_questions=draft_config.opening_questions,
            speech_to_text=draft_config.speech_to_text,
            text_to_speech=draft_config.text_to_speech,
            suggested_after_answer=draft_config.suggested_after_answer,
            review_config=draft_config.review_config,
        )
        db.add(new_config)
        await db.flush()

        new_app.draft_app_config_id = new_config.id
        await db.commit()
        await db.refresh(new_app)
        return new_app

    @staticmethod
    async def get_apps_with_page(
        req: GetAppsWithPageReq, account: Account, db: AsyncSession
    ) -> PageData[AppListItemData]:
        """应用分页列表"""
        filters = [App.account_id == account.id]
        if req.search_word:
            filters.append(App.name.ilike(f"%{req.search_word}%"))

        # 总数
        count_result = await db.execute(
            select(func.count()).select_from(App).where(*filters)
        )
        total_record = count_result.scalar() or 0

        # 分页数据
        result = await db.execute(
            select(App)
            .where(*filters)
            .order_by(desc(App.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        apps = result.scalars().all()

        # 批量获取草稿配置
        items: list[AppListItemData] = []
        for app in apps:
            config = await AppService._get_or_create_draft_config(app.id, db)
            model_name = await AppService._model_display_name(config.model_config, db)
            items.append(AppListItemData.from_model(app, config, model_name))

        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @staticmethod
    async def get_app_detail(
        app_id: UUID, account: Account, db: AsyncSession
    ) -> AppDetailData:
        """应用详情"""
        app = await AppService.get_app(app_id, account, db)
        draft_config = await AppService._get_or_create_draft_config(app_id, db)
        return AppDetailData.from_model(app, draft_config)

    # ===== 阶段7：配置与发布 =====

    @staticmethod
    async def get_draft_app_config(
        app_id: UUID, account: Account, db: AsyncSession,
        app_config_service: "AppConfigService",
    ) -> dict:
        """根据传递的应用id，获取指定的应用草稿配置信息"""
        app = await AppService.get_app(app_id, account, db)
        return await app_config_service.get_draft_app_config(app, db)

    @staticmethod
    async def update_draft_app_config(
        app_id: UUID,
        draft_app_config: dict,
        account: Account,
        db: AsyncSession,
        app_config_service: "AppConfigService",
    ) -> None:
        """根据传递的应用id+草稿配置修改指定应用的最新草稿"""
        app = await AppService.get_app(app_id, account, db)
        from app.services.app_config_validator import validate_draft_app_config
        draft_app_config = await validate_draft_app_config(
            draft_app_config, account, db, app_config_service
        )
        draft_record = await AppService._get_or_create_draft_config(app_id, db)
        for key, value in draft_app_config.items():
            setattr(draft_record, key, value)
        await db.commit()

    @staticmethod
    async def publish_draft_app_config(
        app_id: UUID,
        account: Account,
        db: AsyncSession,
        app_config_service: "AppConfigService",
    ) -> App:
        """发布/更新指定的应用草稿配置为运行时配置"""
        app = await AppService.get_app(app_id, account, db)
        draft_app_config = await app_config_service.get_draft_app_config(app, db)
        user_model_id = (draft_app_config.get("model_config") or {}).get("user_model_id") or ""
        if not user_model_id:
            raise ValidateException("请先在模型管理中添加并选择对话模型")

        app_config = AppConfig(
            app_id=app_id,
            model_config=draft_app_config["model_config"],
            dialog_round=draft_app_config["dialog_round"],
            preset_prompt=draft_app_config["preset_prompt"],
            tools=[
                {
                    "type": tool["type"],
                    "provider_id": tool["provider"]["id"],
                    "tool_id": tool["tool"]["name"],
                    "params": tool["tool"].get("params", {}),
                }
                for tool in draft_app_config["tools"]
            ],
            workflows=[wf["id"] for wf in draft_app_config["workflows"]],
            retrieval_config=draft_app_config["retrieval_config"],
            long_term_memory=draft_app_config["long_term_memory"],
            opening_statement=draft_app_config["opening_statement"],
            opening_questions=draft_app_config["opening_questions"],
            speech_to_text=draft_app_config["speech_to_text"],
            text_to_speech=draft_app_config["text_to_speech"],
            suggested_after_answer=draft_app_config["suggested_after_answer"],
            review_config=draft_app_config["review_config"],
        )
        db.add(app_config)
        await db.flush()

        app.app_config_id = app_config.id
        app.status = AppStatus.PUBLISHED

        from sqlalchemy import delete as sa_delete
        await db.execute(sa_delete(AppDatasetJoin).where(AppDatasetJoin.app_id == app_id))
        for dataset in draft_app_config["datasets"]:
            db.add(AppDatasetJoin(app_id=app_id, dataset_id=dataset["id"]))

        draft_record = await AppService._get_or_create_draft_config(app_id, db)
        from sqlalchemy import func as sa_func
        max_result = await db.execute(
            select(sa_func.coalesce(sa_func.max(AppConfigVersion.version), 0)).where(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED,
            )
        )
        max_version = max_result.scalar() or 0

        new_history = AppConfigVersion(
            app_id=app_id,
            version=max_version + 1,
            config_type=AppConfigType.PUBLISHED,
            model_config=draft_record.model_config,
            dialog_round=draft_record.dialog_round,
            preset_prompt=draft_record.preset_prompt,
            tools=draft_record.tools,
            workflows=draft_record.workflows,
            datasets=draft_record.datasets,
            retrieval_config=draft_record.retrieval_config,
            long_term_memory=draft_record.long_term_memory,
            opening_statement=draft_record.opening_statement,
            opening_questions=draft_record.opening_questions,
            speech_to_text=draft_record.speech_to_text,
            text_to_speech=draft_record.text_to_speech,
            suggested_after_answer=draft_record.suggested_after_answer,
            review_config=draft_record.review_config,
        )
        db.add(new_history)
        await db.commit()
        await db.refresh(app)
        return app

    @staticmethod
    async def cancel_publish_app_config(
        app_id: UUID, account: Account, db: AsyncSession
    ) -> App:
        """取消发布指定的应用配置"""
        app = await AppService.get_app(app_id, account, db)
        if app.status != AppStatus.PUBLISHED:
            raise FailException("当前应用未发布，请核实后重试")
        app.status = AppStatus.DRAFT
        app.app_config_id = None
        from sqlalchemy import delete as sa_delete
        await db.execute(sa_delete(AppDatasetJoin).where(AppDatasetJoin.app_id == app_id))
        await db.commit()
        await db.refresh(app)
        return app

    @staticmethod
    async def get_publish_histories_with_page(
        app_id: UUID,
        req: GetPublishHistoriesWithPageReq,
        account: Account,
        db: AsyncSession,
    ) -> PageData[PublishHistoryItem]:
        """获取指定应用的发布历史配置列表信息"""
        await AppService.get_app(app_id, account, db)
        filters = [
            AppConfigVersion.app_id == app_id,
            AppConfigVersion.config_type == AppConfigType.PUBLISHED,
        ]
        count_result = await db.execute(
            select(func.count()).select_from(AppConfigVersion).where(*filters)
        )
        total_record = count_result.scalar() or 0
        result = await db.execute(
            select(AppConfigVersion)
            .where(*filters)
            .order_by(desc(AppConfigVersion.version))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        versions = result.scalars().all()
        items = [PublishHistoryItem.from_model(v) for v in versions]
        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @staticmethod
    async def fallback_history_to_draft(
        app_id: UUID,
        app_config_version_id: UUID,
        account: Account,
        db: AsyncSession,
        app_config_service: "AppConfigService",
    ) -> None:
        """根据传递的应用id、历史配置版本id、账号信息，回退特定配置到草稿"""
        app = await AppService.get_app(app_id, account, db)
        result = await db.execute(
            select(AppConfigVersion).where(AppConfigVersion.id == app_config_version_id)
        )
        app_config_version = result.scalar_one_or_none()
        if not app_config_version:
            raise NotFoundException("该历史版本配置不存在，请核实后重试")

        draft_app_config = {
            "model_config": app_config_version.model_config,
            "dialog_round": app_config_version.dialog_round,
            "preset_prompt": app_config_version.preset_prompt,
            "tools": app_config_version.tools,
            "workflows": app_config_version.workflows,
            "datasets": app_config_version.datasets,
            "retrieval_config": app_config_version.retrieval_config,
            "long_term_memory": app_config_version.long_term_memory,
            "opening_statement": app_config_version.opening_statement,
            "opening_questions": app_config_version.opening_questions,
            "speech_to_text": app_config_version.speech_to_text,
            "text_to_speech": app_config_version.text_to_speech,
            "suggested_after_answer": app_config_version.suggested_after_answer,
            "review_config": app_config_version.review_config,
        }
        from app.services.app_config_validator import validate_draft_app_config
        draft_app_config = await validate_draft_app_config(
            draft_app_config, account, db, app_config_service
        )
        draft_record = await AppService._get_or_create_draft_config(app_id, db)
        for key, value in draft_app_config.items():
            setattr(draft_record, key, value)
        await db.commit()

    @staticmethod
    async def get_published_config(
        app_id: UUID, account: Account, db: AsyncSession
    ) -> dict:
        """获取应用的发布配置"""
        app = await AppService.get_app(app_id, account, db)
        token = app.token if app.token else ""
        return {
            "web_app": {
                "token": token,
                "status": app.status,
            }
        }

    @staticmethod
    async def regenerate_web_app_token(
        app_id: UUID, account: Account, db: AsyncSession
    ) -> str:
        """重新生成 WebApp 凭证标识"""
        app = await AppService.get_app(app_id, account, db)
        if app.status != AppStatus.PUBLISHED:
            raise FailException("应用未发布，无法生成WebApp凭证标识")
        token = generate_random_string(16)
        app.token = token
        await db.commit()
        return token

    # ===== 阶段8：调试会话与流式 =====

    @staticmethod
    async def _get_or_create_debug_conversation(
        app: App, db: AsyncSession
    ) -> Conversation:
        """获取或创建应用的调试会话"""
        debug_conversation = None
        if app.debug_conversation_id is not None:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == app.debug_conversation_id,
                    Conversation.invoke_from == InvokeFrom.DEBUGGER,
                )
            )
            debug_conversation = result.scalar_one_or_none()

        if not app.debug_conversation_id or not debug_conversation:
            debug_conversation = Conversation(
                app_id=app.id,
                name="New Conversation",
                invoke_from=InvokeFrom.DEBUGGER,
                created_by=app.account_id,
            )
            db.add(debug_conversation)
            await db.flush()
            app.debug_conversation_id = debug_conversation.id
            await db.commit()
            await db.refresh(app)

        return debug_conversation

    @staticmethod
    async def get_debug_conversation_summary(
        app_id: UUID, account: Account, db: AsyncSession, app_config_service
    ) -> str:
        """根据传递的应用id+账号获取指定应用的调试会话长期记忆"""
        app = await AppService.get_app(app_id, account, db)
        draft_app_config = await app_config_service.get_draft_app_config(app, db)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("该应用并未开启长期记忆，无法获取")
        debug_conversation = await AppService._get_or_create_debug_conversation(app, db)
        return debug_conversation.summary

    @staticmethod
    async def update_debug_conversation_summary(
        app_id: UUID, summary: str, account: Account, db: AsyncSession, app_config_service
    ) -> Conversation:
        """根据传递的应用id+总结更新指定应用的调试长期记忆"""
        app = await AppService.get_app(app_id, account, db)
        draft_app_config = await app_config_service.get_draft_app_config(app, db)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("该应用并未开启长期记忆，无法获取")
        debug_conversation = await AppService._get_or_create_debug_conversation(app, db)
        debug_conversation.summary = summary
        await db.commit()
        return debug_conversation

    @staticmethod
    async def delete_debug_conversation(
        app_id: UUID, account: Account, db: AsyncSession
    ) -> App:
        """根据传递的应用id，删除指定的应用调试会话"""
        app = await AppService.get_app(app_id, account, db)
        if not app.debug_conversation_id:
            return app
        app.debug_conversation_id = None
        await db.commit()
        return app

    @staticmethod
    async def debug_chat(
        app_id: UUID,
        req: DebugChatReq,
        account: Account,
        db: AsyncSession,
        app_config_service,
        language_model_service,
        retrieval_service,
        sync_redis,
    ) -> AsyncGenerator[str, None]:
        """根据传递的应用id+提问query向特定的应用发起会话调试（SSE 流式）"""
        try:
            # 1.获取应用信息并校验权限
            app = await AppService.get_app(app_id, account, db)

            # 2.获取应用的最新草稿配置信息
            draft_app_config = await app_config_service.get_draft_app_config(app, db)

            # 3.获取当前应用的调试会话信息
            debug_conversation = await AppService._get_or_create_debug_conversation(app, db)

            # 4.新建一条消息记录
            message = Message(
                app_id=app_id,
                conversation_id=debug_conversation.id,
                invoke_from=InvokeFrom.DEBUGGER,
                created_by=account.id,
                query=req.query,
                image_urls=req.image_urls,
                status=MessageStatus.NORMAL,
            )
            db.add(message)
            await db.flush()

            # 5.从语言模型管理器中加载大语言模型
            llm = language_model_service.load_language_model(draft_app_config.get("model_config", {}))

            # 6.实例化TokenBufferMemory用于提取短期记忆
            token_buffer_memory = TokenBufferMemory(
                db=db,
                conversation=debug_conversation,
                model_instance=llm,
            )
            history = await token_buffer_memory.get_history_prompt_messages(
                message_limit=draft_app_config["dialog_round"],
            )

            # 7.将草稿配置中的tools转换成LangChain工具
            tools = await app_config_service.get_langchain_tools_by_tools_config(
                draft_app_config["tools"], db
            )

            # 8.检测是否关联了知识库
            if draft_app_config["datasets"]:
                dataset_retrieval = retrieval_service.create_langchain_tool_from_search(
                    dataset_ids=[dataset["id"] for dataset in draft_app_config["datasets"]],
                    account_id=account.id,
                    retrieval_strategy=draft_app_config["retrieval_config"]["retrieval_strategy"],
                    k=draft_app_config["retrieval_config"]["k"],
                    score=draft_app_config["retrieval_config"]["score"],
                    retrival_source=RetrievalSource.APP,
                )
                tools.append(dataset_retrieval)

            # 9.检测是否关联工作流
            if draft_app_config["workflows"]:
                workflow_tools = await app_config_service.get_langchain_tools_by_workflow_ids(
                    [workflow["id"] for workflow in draft_app_config["workflows"]], db
                )
                tools.extend(workflow_tools)

            # 10.根据LLM是否支持tool_call决定使用不同的Agent
            agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReACTAgent
            agent = agent_class(
                llm=llm,
                agent_config=AgentConfig(
                    user_id=account.id,
                    invoke_from=InvokeFrom.DEBUGGER,
                    preset_prompt=draft_app_config["preset_prompt"],
                    enable_long_term_memory=draft_app_config["long_term_memory"]["enable"],
                    tools=tools,
                    review_config=draft_app_config["review_config"],
                ),
                sync_redis=sync_redis,
            )

            # 11.流式输出
            sync_gen = agent.stream({
                "messages": [llm.convert_to_human_message(req.query, req.image_urls)],
                "history": history,
                "long_term_memory": debug_conversation.summary,
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

                # 12.将数据填充到agent_thought，便于存储到数据库服务中
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
                    "conversation_id": str(debug_conversation.id),
                    "message_id": str(message.id),
                    "task_id": str(agent_thought.task_id),
                }
                yield f"event: {queue_event_name(agent_thought.event)}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n"

            # 12.将消息以及推理过程添加到数据库
            await ConversationService().save_agent_thoughts(
                account_id=account.id,
                app_id=app.id,
                app_config=draft_app_config,
                conversation_id=debug_conversation.id,
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
    async def stop_debug_chat(
        app_id: UUID, task_id: UUID, account: Account, db: AsyncSession, sync_redis
    ) -> None:
        """根据传递的应用id+任务id+账号，停止某个应用的调试会话，中断流式事件"""
        await AppService.get_app(app_id, account, db)
        from app.core.agent.agents import AgentQueueManager
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER, account.id, sync_redis)

    @staticmethod
    async def get_debug_conversation_messages_with_page(
        app_id: UUID,
        req: GetDebugConversationMessagesWithPageReq,
        account: Account,
        db: AsyncSession,
        app_config_service,
    ) -> PageData:
        """根据传递的应用id+请求数据，获取调试会话消息列表分页数据"""
        app = await AppService.get_app(app_id, account, db)
        debug_conversation = await AppService._get_or_create_debug_conversation(app, db)

        # 构建游标条件
        filters = [
            Message.conversation_id == debug_conversation.id,
            Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
            Message.answer != "",
            Message.is_deleted == False,  # noqa: E712
        ]
        from datetime import datetime
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
    def auto_create_app(name: str, description: str, account_id: UUID) -> None:
        """根据名称、描述、账号id利用 AI 创建一个 Agent（Celery 同步任务）。"""
        import hashlib
        import io
        import uuid as uuid_lib
        from datetime import datetime

        import requests
        from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnableParallel
        from langchain_openai import ChatOpenAI
        from minio import Minio

        from app.config import settings
        from app.core.observability import langfuse_callbacks
        from app.db import SyncSessionLocal
        from app.entities.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
        from app.models.upload_file import UploadFile
        from app.services.upload_file_service import UploadFileService

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.8, callbacks=langfuse_callbacks())
        dalle_api_wrapper = DallEAPIWrapper(model="dall-e-3", size="1024x1024")
        generate_icon_chain = (
            ChatPromptTemplate.from_template(GENERATE_ICON_PROMPT_TEMPLATE)
            | llm
            | StrOutputParser()
            | dalle_api_wrapper.run
        )
        generate_preset_prompt_chain = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE),
            ("human", "应用名称: {name}\n\n应用描述: {description}"),
        ]) | llm | StrOutputParser()
        generate_app_config_chain = RunnableParallel({
            "icon": generate_icon_chain,
            "preset_prompt": generate_preset_prompt_chain,
        })
        app_config = generate_app_config_chain.invoke({"name": name, "description": description})

        icon_response = requests.get(app_config.get("icon"), timeout=60)
        if icon_response.status_code != 200:
            raise FailException("生成应用icon图标出错")
        icon_content = icon_response.content

        now = datetime.now()
        object_key = f"{now.year}/{now.month:02d}/{now.day:02d}/{uuid_lib.uuid4()}.png"
        minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=False,
        )
        bucket = settings.MINIO_BUCKET
        UploadFileService.ensure_bucket(minio_client)
        minio_client.put_object(
            bucket_name=bucket,
            object_name=object_key,
            data=io.BytesIO(icon_content),
            length=len(icon_content),
            content_type="image/png",
        )
        icon = UploadFileService.get_file_url(object_key)

        with SyncSessionLocal() as db:
            account = db.get(Account, account_id)
            if account is None:
                return
            db.add(UploadFile(
                account_id=account.id,
                name="icon.png",
                key=object_key,
                size=len(icon_content),
                extension="png",
                mime_type="image/png",
                hash=hashlib.sha3_256(icon_content).hexdigest(),
            ))
            app = App(
                account_id=account.id,
                name=name,
                icon=icon,
                description=description,
                status=AppStatus.DRAFT,
            )
            db.add(app)
            db.flush()
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **{
                    **DEFAULT_APP_CONFIG,
                    "preset_prompt": app_config.get("preset_prompt", ""),
                },
            )
            db.add(app_config_version)
            db.flush()
            app.draft_app_config_id = app_config_version.id
            db.commit()
