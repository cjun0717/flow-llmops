#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 8：会话 CRUD + 调试会话冒烟测试。

注意：debug_chat SSE 流式依赖 OpenAI API（真实 LLM 调用），
无 OPENAI_API_KEY 时跳过该用例；其余 CRUD 用例仅需数据库。
"""
from __future__ import annotations

import os
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.entities.conversation_entity import InvokeFrom, MessageStatus
from app.main import create_app
from app.models.account import Account
from app.models.conversation import Conversation, Message, MessageAgentThought
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase8@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段8测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段8联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段8联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段8联调: {e}")
        raise

    async with AsyncSessionLocal() as db:
        account = await AccountService.ensure_account(
            email=TEST_EMAIL,
            password=TEST_PASSWORD,
            name=TEST_NAME,
            db=db,
        )
        password_hashed, password_salt = AccountService._encode_password(TEST_PASSWORD)
        account.password = password_hashed
        account.password_salt = password_salt
        account.name = TEST_NAME
        await db.commit()

    return create_access_token(account.id)


async def _get_account_id() -> UUID:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Account).where(Account.email == TEST_EMAIL))
        account = result.scalar_one()
        return account.id


async def _create_debug_conversation(app_id: UUID, account_id: UUID) -> UUID:
    """直接在数据库中创建一个调试会话并返回其id"""
    async with AsyncSessionLocal() as db:
        conversation = Conversation(
            app_id=app_id,
            name="测试会话",
            invoke_from=InvokeFrom.DEBUGGER,
            created_by=account_id,
        )
        db.add(conversation)
        await db.flush()
        conversation_id = conversation.id

        message = Message(
            app_id=app_id,
            conversation_id=conversation_id,
            invoke_from=InvokeFrom.DEBUGGER,
            created_by=account_id,
            query="你好",
            answer="你好，有什么可以帮你？",
            status=MessageStatus.NORMAL,
        )
        db.add(message)
        await db.flush()
        message_id = message.id

        thought = MessageAgentThought(
            app_id=app_id,
            conversation_id=conversation_id,
            message_id=message_id,
            invoke_from=InvokeFrom.DEBUGGER,
            created_by=account_id,
            position=1,
            event="agent_message",
            thought="你好，有什么可以帮你？",
            answer="你好，有什么可以帮你？",
        )
        db.add(thought)
        await db.commit()
        return conversation_id
@pytest.mark.asyncio
async def test_phase8_conversation_crud(app, auth_token):
    """会话 CRUD 完整流程：创建会话→消息列表→改名→置顶→删消息→删会话"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    account_id = await _get_account_id()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建应用
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={
                "name": "阶段8应用",
                "icon": "https://example.com/icon.png",
                "description": "阶段8测试",
            },
        )
        assert r.status_code == 200, r.text
        app_id = r.json()["data"]["id"]

        # 2. 直接创建调试会话+消息
        conversation_id = await _create_debug_conversation(UUID(app_id), account_id)

        # 3. 获取会话消息列表
        r = await client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        assert body["data"]["paginator"]["total_record"] >= 1
        items = body["data"]["list"]
        assert len(items) >= 1
        assert items[0]["query"] == "你好"
        assert items[0]["answer"] == "你好，有什么可以帮你？"
        assert len(items[0]["agent_thoughts"]) >= 1
        message_id = items[0]["id"]

        # 4. 获取会话名称
        r = await client.get(
            f"/api/v1/conversations/{conversation_id}/name", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "测试会话"

        # 5. 修改会话名称
        r = await client.post(
            f"/api/v1/conversations/{conversation_id}/name",
            headers=headers,
            json={"name": "改名后的会话"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        r = await client.get(
            f"/api/v1/conversations/{conversation_id}/name", headers=headers
        )
        assert r.json()["data"]["name"] == "改名后的会话"

        # 6. 修改置顶状态
        r = await client.post(
            f"/api/v1/conversations/{conversation_id}/is-pinned",
            headers=headers,
            json={"is_pinned": True},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        # 7. 删除消息
        r = await client.post(
            f"/api/v1/conversations/{conversation_id}/messages/{message_id}/delete",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        # 删除后消息列表为空
        r = await client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=headers
        )
        assert r.json()["data"]["paginator"]["total_record"] == 0

        # 8. 删除会话
        r = await client.post(
            f"/api/v1/conversations/{conversation_id}/delete", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        # 删除后再访问会话名称应 not_found
        r = await client.get(
            f"/api/v1/conversations/{conversation_id}/name", headers=headers
        )
        assert r.json()["code"] == "not_found"

        # 9. 清理应用
        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
@pytest.mark.asyncio
async def test_phase8_debug_summary(app, auth_token):
    """调试会话长期记忆：未开启返回 fail，开启后可读取"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={
                "name": "阶段8长期记忆应用",
                "icon": "https://example.com/icon.png",
                "description": "长期记忆测试",
            },
        )
        app_id = r.json()["data"]["id"]

        # 默认未开启长期记忆 → fail
        r = await client.get(f"/api/v1/apps/{app_id}/summary", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == "fail", r.json()

        # 开启长期记忆
        r = await client.post(
            f"/api/v1/apps/{app_id}/draft-app-config",
            headers=headers,
            json={"long_term_memory": {"enable": True}},
        )
        assert r.json()["code"] == "success", r.json()

        # 开启后可读取（空摘要）
        r = await client.get(f"/api/v1/apps/{app_id}/summary", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == "success"
        assert r.json()["data"]["summary"] == ""

        # 更新摘要
        r = await client.post(
            f"/api/v1/apps/{app_id}/summary",
            headers=headers,
            json={"summary": "这是一段长期记忆摘要"},
        )
        assert r.json()["code"] == "success"

        # 读取确认
        r = await client.get(f"/api/v1/apps/{app_id}/summary", headers=headers)
        assert r.json()["data"]["summary"] == "这是一段长期记忆摘要"

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_phase8_debug_messages_and_delete(app, auth_token):
    """调试会话消息列表 + 清空调试会话"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={
                "name": "阶段8调试消息应用",
                "icon": "https://example.com/icon.png",
                "description": "调试消息测试",
            },
        )
        app_id = r.json()["data"]["id"]

        # 获取调试会话消息列表（首次会自动创建调试会话，列表为空）
        r = await client.get(
            f"/api/v1/apps/{app_id}/conversations/messages", headers=headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success"
        assert r.json()["data"]["paginator"]["total_record"] == 0

        # 清空调试会话
        r = await client.post(
            f"/api/v1/apps/{app_id}/conversations/delete-debug-conversation",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_phase8_debug_chat_sse(app, auth_token):
    """调试会话 SSE 流式：依赖 OpenAI API，无 key 时跳过"""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("未设置 OPENAI_API_KEY，跳过 SSE 流式联调")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={
                "name": "阶段8SSE应用",
                "icon": "https://example.com/icon.png",
                "description": "SSE测试",
            },
        )
        app_id = r.json()["data"]["id"]

        # 发起调试对话（SSE 流式）
        async with client.stream(
            "POST",
            f"/api/v1/apps/{app_id}/conversations",
            headers=headers,
            json={"query": "你好", "image_urls": []},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            # 读取部分流式数据，至少应收到一个事件
            received = 0
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    received += 1
                if received >= 1:
                    break
            assert received >= 1, "未收到任何 SSE 事件"

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
