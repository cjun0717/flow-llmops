#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 11.1：AI 辅助冒烟测试。

不依赖 Docker 的用例会实际跑通（schema 校验、SSE 格式、权限拦截）。
需要数据库的联调用例在 DB 不可用时 skip。
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.exceptions import ForbiddenException
from app.main import create_app
from app.schemas.ai import GenerateSuggestedQuestionsReq, OptimizePromptReq
from app.services.ai_service import AIService


# ===== 不依赖外部服务的单测 =====


def test_optimize_prompt_req_valid():
    req = OptimizePromptReq(prompt="你是一个助手")
    assert req.prompt == "你是一个助手"


def test_optimize_prompt_req_empty():
    with pytest.raises(ValidationError):
        OptimizePromptReq(prompt="")


def test_optimize_prompt_req_too_long():
    with pytest.raises(ValidationError):
        OptimizePromptReq(prompt="x" * 2001)


def test_generate_suggested_questions_req_valid():
    msg_id = uuid4()
    req = GenerateSuggestedQuestionsReq(message_id=msg_id)
    assert req.message_id == msg_id


def test_generate_suggested_questions_req_invalid_uuid():
    with pytest.raises(ValidationError):
        GenerateSuggestedQuestionsReq(message_id="not-a-uuid")


@pytest.mark.asyncio
async def test_optimize_prompt_sse_format():
    """SSE 事件格式必须是 event: optimize_prompt + data JSON，前端会累加 optimize_prompt"""

    class FakeChain:
        def stream(self, _inputs):
            yield "你是"
            yield "一位助手"

    with patch.object(AIService, "_build_optimize_chain", return_value=FakeChain()):
        events = []
        async for chunk in AIService.optimize_prompt("写一个助手"):
            events.append(chunk)

    assert len(events) == 2
    for event in events:
        assert event.startswith("event: optimize_prompt\n")
        assert "data: " in event
        payload = json.loads(event.split("data: ", 1)[1].strip())
        assert "optimize_prompt" in payload

    texts = [
        json.loads(event.split("data: ", 1)[1].strip())["optimize_prompt"]
        for event in events
    ]
    assert "".join(texts) == "你是一位助手"


@pytest.mark.asyncio
async def test_optimize_prompt_error_event():
    """LLM 调用失败时输出 error 事件，不抛到路由层"""

    class BrokenChain:
        def stream(self, _inputs):
            raise RuntimeError("llm unavailable")
            yield  # pragma: no cover

    with patch.object(AIService, "_build_optimize_chain", return_value=BrokenChain()):
        events = []
        async for chunk in AIService.optimize_prompt("写一个助手"):
            events.append(chunk)

    assert len(events) == 1
    assert events[0].startswith("event: error\n")
    payload = json.loads(events[0].split("data:", 1)[1].strip())
    assert payload["code"] == "fail"
    assert "llm unavailable" in payload["message"]


@pytest.mark.asyncio
async def test_generate_suggested_questions_forbidden_when_missing():
    """消息不存在时返回无权限"""
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=MagicMock(return_value=None))
    account = SimpleNamespace(id=uuid4())

    with pytest.raises(ForbiddenException) as exc:
        await AIService.generate_suggested_questions_from_message_id(uuid4(), account, db)
    assert "不存在或无权限" in exc.value.message


@pytest.mark.asyncio
async def test_generate_suggested_questions_forbidden_when_owner_mismatch():
    """消息不属于当前账号时返回无权限"""
    db = AsyncMock()
    message = SimpleNamespace(created_by=uuid4(), query="你好", answer="你好呀")
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=MagicMock(return_value=message))
    account = SimpleNamespace(id=uuid4())

    with pytest.raises(ForbiddenException):
        await AIService.generate_suggested_questions_from_message_id(uuid4(), account, db)


@pytest.mark.asyncio
async def test_generate_suggested_questions_success():
    """权限通过后调用会话服务生成建议问题"""
    db = AsyncMock()
    account_id = uuid4()
    message = SimpleNamespace(created_by=account_id, query="天气如何", answer="今天晴朗")
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=MagicMock(return_value=message))
    account = SimpleNamespace(id=account_id)

    with patch(
        "app.services.ai_service.ConversationService.generate_suggested_questions",
        return_value=["明天会下雨吗？", "适合出门吗？", "温度多少？"],
    ) as mocked:
        questions = await AIService.generate_suggested_questions_from_message_id(
            uuid4(), account, db
        )

    assert questions == ["明天会下雨吗？", "适合出门吗？", "温度多少？"]
    mocked.assert_called_once_with("Human: 天气如何\nAI: 今天晴朗")


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
        pytest.skip(f"数据库不可用，跳过阶段11.1联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段11.1联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段11.1联调: {e}")
        raise

    async with AsyncSessionLocal() as db:
        account = await AccountService.ensure_account(
            email="phase11-ai@test.local",
            password="Test1234",
            name="阶段11.1测试账号",
            db=db,
        )
        password_hashed, password_salt = AccountService._encode_password("Test1234")
        account.password = password_hashed
        account.password_salt = password_salt
        account.name = "阶段11.1测试账号"
        await db.commit()

    return create_access_token(account.id)


@pytest.mark.asyncio
async def test_ai_routes_unauthorized(app, auth_token):
    """未登录访问 AI 接口应 unauthorized"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/ai/optimize-prompt", json={"prompt": "写一个助手"})
        assert r.json()["code"] == "unauthorized"

        r = await client.post(
            "/api/v1/ai/suggested-questions",
            json={"message_id": str(uuid4())},
        )
        assert r.json()["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_ai_routes_validate_error(app, auth_token):
    """登录后请求体校验失败"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/ai/optimize-prompt", headers=headers, json={"prompt": ""})
        assert r.json()["code"] == "validate_error"

        r = await client.post(
            "/api/v1/ai/suggested-questions",
            headers=headers,
            json={"message_id": "bad"},
        )
        assert r.json()["code"] == "validate_error"


@pytest.mark.asyncio
async def test_suggested_questions_forbidden_via_http(app, auth_token):
    """登录后对不存在的消息生成建议问题应 forbidden"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/ai/suggested-questions",
            headers=headers,
            json={"message_id": str(uuid4())},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "forbidden"
