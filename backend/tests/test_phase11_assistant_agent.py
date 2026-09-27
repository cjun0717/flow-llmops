#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 11.3：辅助 Agent 冒烟测试。

不依赖 Docker 的用例会实际跑通（schema 校验、create_app 工具、LLM 加载）。
需要数据库的联调用例在 DB 不可用时 skip。
SSE 流式依赖 OpenAI API，无 key 时跳过。
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME
from app.main import create_app
from app.schemas.assistant_agent import (
    AssistantAgentChatReq,
    GetAssistantAgentMessagesWithPageReq,
)
from app.services.assistant_agent_service import AssistantAgentService


# ===== 不依赖外部服务的单测 =====


def test_chat_req_valid():
    req = AssistantAgentChatReq(query="帮我创建一个能回答LLM问题的Agent。")
    assert req.query.startswith("帮我创建")
    assert req.image_urls == []


def test_chat_req_empty_query():
    with pytest.raises(ValidationError):
        AssistantAgentChatReq(query="")


def test_chat_req_too_many_images():
    with pytest.raises(ValidationError):
        AssistantAgentChatReq(
            query="你好",
            image_urls=[f"https://example.com/{i}.png" for i in range(6)],
        )


def test_chat_req_invalid_image_url():
    with pytest.raises(ValidationError):
        AssistantAgentChatReq(query="你好", image_urls=["not-a-url"])


def test_messages_page_req_defaults():
    req = GetAssistantAgentMessagesWithPageReq()
    assert req.current_page == 1
    assert req.page_size == 20
    assert req.created_at == 0


def test_create_app_tool_dispatches_celery():
    account_id = uuid4()
    with patch("app.tasks.app_task.auto_create_app.delay") as delay:
        tool = AssistantAgentService.convert_create_app_to_tool(account_id)
        assert tool.name == "create_app"
        result = tool.invoke({"name": "知识问答助手", "description": "回答 LLM 相关问题"})
        delay.assert_called_once_with("知识问答助手", "回答 LLM 相关问题", str(account_id))
        assert "已调用后端异步任务创建Agent应用" in result
        assert "知识问答助手" in result


def test_load_assistant_agent_llm():
    """从 settings 组装模型配置并交给 LanguageModelService，不真正连 OpenAI"""
    svc = MagicMock()
    svc.load_language_model.return_value = MagicMock(name="llm")
    llm = AssistantAgentService.load_assistant_agent_llm(svc)
    assert llm is svc.load_language_model.return_value
    config = svc.load_language_model.call_args[0][0]
    assert config["provider"] == settings.ASSISTANT_AGENT_MODEL_PROVIDER
    assert config["model"] == settings.ASSISTANT_AGENT_MODEL
    assert config["parameters"]["temperature"] == settings.ASSISTANT_AGENT_TEMPERATURE
    assert config["parameters"]["max_tokens"] == settings.ASSISTANT_AGENT_MAX_TOKENS


def test_assistant_knowledge_tool_name():
    """convert_to_tool 返回的工具名必须是 dataset_retrieval"""
    from langchain_core.tools import BaseTool

    from app.services.assistant_knowledge_service import AssistantKnowledgeService

    svc = AssistantKnowledgeService(client=MagicMock(), embeddings_service=MagicMock())
    svc.search = MagicMock(return_value=[])  # type: ignore[method-assign]
    tool = svc.convert_to_tool()
    assert isinstance(tool, BaseTool)
    assert tool.name == DATASET_RETRIEVAL_TOOL_NAME
    assert tool.invoke({"query": "LLMOps"}) == "知识库内没有检索到对应内容"
    svc.search.assert_called_once_with("LLMOps", top_k=5)


def test_assistant_knowledge_seed_docs():
    """课程知识种子从 JSON 加载，不再依赖 FAISS 二进制索引"""
    from app.services.assistant_knowledge_service import AssistantKnowledgeService

    svc = AssistantKnowledgeService(client=MagicMock(), embeddings_service=MagicMock())
    docs = svc._load_seed_docs()
    assert len(docs) == 260
    assert docs[0]["id"]
    assert "LLMOps" in docs[0]["text"] or "API" in docs[0]["text"]


def test_stop_chat_sets_flag():
    account = MagicMock()
    account.id = uuid4()
    task_id = uuid4()
    redis = MagicMock()
    redis.get.return_value = f"account-{account.id}"

    AssistantAgentService.stop_chat(task_id, account, redis)
    redis.setex.assert_called_once()
    args, _kwargs = redis.setex.call_args
    assert "generate_task_stopped" in args[0]


@pytest.mark.asyncio
async def test_chat_yields_error_event():
    """会话准备失败时输出 error 事件，不抛到路由层"""
    req = AssistantAgentChatReq(query="你好")
    account = MagicMock()
    with patch.object(
        AssistantAgentService,
        "_get_or_create_assistant_conversation",
        side_effect=RuntimeError("boom"),
    ):
        events = []
        async for chunk in AssistantAgentService.chat(
            req, account, MagicMock(), MagicMock(), MagicMock(), MagicMock()
        ):
            events.append(chunk)

    assert len(events) == 1
    assert events[0].startswith("event: error\n")
    payload = json.loads(events[0].split("data:", 1)[1].strip())
    assert payload["code"] == "fail"
    assert "boom" in payload["message"]


# ===== 需数据库的联调（DB 不可用时 skip） =====


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    from app.db import AsyncSessionLocal, init_create_table
    from app.services.account_service import AccountService
    from app.utils.jwt import create_access_token

    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段11.3联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段11.3联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段11.3联调: {e}")
        raise

    async with AsyncSessionLocal() as db:
        account = await AccountService.ensure_account(
            email="phase11-assistant-agent@test.local",
            password="Test1234",
            name="阶段11.3测试账号",
            db=db,
        )
        password_hashed, password_salt = AccountService._encode_password("Test1234")
        account.password = password_hashed
        account.password_salt = password_salt
        account.name = "阶段11.3测试账号"
        await db.commit()

    return create_access_token(account.id)


@pytest.mark.asyncio
async def test_assistant_agent_routes_unauthorized(app, auth_token):
    """未登录访问辅助 Agent 接口应 unauthorized"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/assistant-agent/chat", json={"query": "你好"})
        assert r.json()["code"] == "unauthorized"

        r = await client.post(f"/api/v1/assistant-agent/chat/{uuid4()}/stop")
        assert r.json()["code"] == "unauthorized"

        r = await client.get("/api/v1/assistant-agent/messages")
        assert r.json()["code"] == "unauthorized"

        r = await client.post("/api/v1/assistant-agent/delete-conversation")
        assert r.json()["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_assistant_agent_chat_validate_error(app, auth_token):
    """登录后 query 为空应校验失败"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/assistant-agent/chat",
            headers=headers,
            json={"query": ""},
        )
        assert r.json()["code"] == "validate_error"


@pytest.mark.asyncio
async def test_assistant_agent_messages_and_delete(app, auth_token):
    """分页消息首次为空；清空会话后仍可再次拉取空列表"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/assistant-agent/messages", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        assert body["data"]["list"] == []
        assert body["data"]["paginator"]["total_record"] == 0

        r = await client.post("/api/v1/assistant-agent/delete-conversation", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        r = await client.get("/api/v1/assistant-agent/messages", headers=headers)
        assert r.json()["code"] == "success"
        assert r.json()["data"]["list"] == []


@pytest.mark.asyncio
async def test_assistant_agent_stop_chat(app, auth_token):
    """停止不存在的任务应静默成功（任务未执行则不设置 stop flag）"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            r = await client.post(
                f"/api/v1/assistant-agent/chat/{uuid4()}/stop",
                headers=headers,
            )
        except Exception as e:
            if "connect" in str(e).lower() or "refused" in str(e).lower():
                pytest.skip(f"Redis 不可用，跳过停止会话联调: {e}")
            raise
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success"


@pytest.mark.asyncio
async def test_assistant_agent_chat_sse(app, auth_token):
    """辅助 Agent SSE 流式：依赖 OpenAI API，无 key 时跳过"""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("未设置 OPENAI_API_KEY，跳过 SSE 流式联调")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        async with client.stream(
            "POST",
            "/api/v1/assistant-agent/chat",
            headers=headers,
            json={"query": "你好", "image_urls": []},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            received = 0
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    received += 1
                if received >= 1:
                    break
            assert received >= 1, "未收到任何 SSE 事件"
