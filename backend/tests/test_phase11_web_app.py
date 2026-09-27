#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 11.5：WebApp 冒烟测试。

schema / 权限 / 会话列表不依赖 LLM；SSE 流式无 OPENAI_API_KEY 时跳过。
"""
from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.entities.conversation_entity import InvokeFrom
from app.main import create_app
from app.schemas.web_app import WebAppChatReq


def test_chat_req_valid():
    req = WebAppChatReq(query="你好")
    assert req.conversation_id == ""
    assert req.image_urls == []


def test_chat_req_empty_query():
    with pytest.raises(ValidationError):
        WebAppChatReq(query="")


def test_chat_req_invalid_conversation_id():
    with pytest.raises(ValidationError):
        WebAppChatReq(query="你好", conversation_id="not-a-uuid")


def test_chat_req_too_many_images():
    with pytest.raises(ValidationError):
        WebAppChatReq(
            query="你好",
            image_urls=[f"https://example.com/{i}.png" for i in range(6)],
        )


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
        pytest.skip(f"数据库不可用，跳过阶段11.5联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段11.5联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段11.5联调: {e}")
        raise

    async with AsyncSessionLocal() as db:
        account = await AccountService.ensure_account(
            email="phase11-webapp@test.local",
            password="Test1234",
            name="阶段11.5测试账号",
            db=db,
        )
        password_hashed, password_salt = AccountService._encode_password("Test1234")
        account.password = password_hashed
        account.password_salt = password_salt
        account.name = "阶段11.5测试账号"
        await db.commit()

    return create_access_token(account.id)


async def _publish_and_token(client: AsyncClient, headers: dict) -> tuple[str, str]:
    r = await client.post(
        "/api/v1/apps",
        headers=headers,
        json={"name": "WebApp测试", "icon": "https://example.com/i.png", "description": "web"},
    )
    assert r.json()["code"] == "success", r.text
    app_id = r.json()["data"]["id"]

    r = await client.post(
        f"/api/v1/apps/{app_id}/draft-app-config",
        headers=headers,
        json={
            "opening_statement": "你好，我是WebApp助手",
            "opening_questions": ["你能做什么？"],
        },
    )
    assert r.json()["code"] == "success", r.text

    r = await client.post(f"/api/v1/apps/{app_id}/publish", headers=headers)
    assert r.json()["code"] == "success", r.text

    r = await client.post(
        f"/api/v1/apps/{app_id}/published-config/regenerate-web-app-token",
        headers=headers,
    )
    assert r.json()["code"] == "success", r.text
    token = r.json()["data"]["token"]
    assert token
    return app_id, token


@pytest.mark.asyncio
async def test_web_app_unauthorized(app, auth_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/web-apps/sometoken")
        assert r.json()["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_web_app_token_not_found(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/web-apps/not-exist-token", headers=headers)
        assert r.json()["code"] == "not_found"


@pytest.mark.asyncio
async def test_web_app_info_and_conversations(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_id, token = await _publish_and_token(client, headers)

        r = await client.get(f"/api/v1/web-apps/{token}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        data = body["data"]
        assert data["id"] == app_id
        assert data["name"] == "WebApp测试"
        assert data["app_config"]["opening_statement"] == "你好，我是WebApp助手"
        assert data["app_config"]["opening_questions"] == ["你能做什么？"]
        assert "enable" in data["app_config"]["suggested_after_answer"]
        assert isinstance(data["app_config"]["features"], list)

        r = await client.get(
            f"/api/v1/web-apps/{token}/conversations",
            headers=headers,
            params={"is_pinned": False},
        )
        assert r.json()["code"] == "success"
        assert r.json()["data"] == []

        r = await client.post(
            f"/api/v1/web-apps/{token}/chat/{uuid4()}/stop",
            headers=headers,
        )
        assert r.json()["code"] == "success"

        r = await client.post(
            f"/api/v1/web-apps/{token}/chat",
            headers=headers,
            json={"query": ""},
        )
        assert r.json()["code"] == "validate_error"

        await client.post(f"/api/v1/apps/{app_id}/cancel-publish", headers=headers)
        r = await client.get(f"/api/v1/web-apps/{token}", headers=headers)
        assert r.json()["code"] == "not_found"

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_web_app_conversations_filter_pinned(app, auth_token):
    from app.db import AsyncSessionLocal
    from app.models.account import Account
    from app.models.conversation import Conversation
    from sqlalchemy import select

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_id, token = await _publish_and_token(client, headers)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Account).where(Account.email == "phase11-webapp@test.local"))
            account = result.scalar_one()
            db.add(Conversation(
                app_id=UUID(app_id),
                name="普通会话",
                invoke_from=InvokeFrom.WEB_APP,
                created_by=account.id,
                is_pinned=False,
            ))
            db.add(Conversation(
                app_id=UUID(app_id),
                name="置顶会话",
                invoke_from=InvokeFrom.WEB_APP,
                created_by=account.id,
                is_pinned=True,
            ))
            await db.commit()

        r = await client.get(
            f"/api/v1/web-apps/{token}/conversations",
            headers=headers,
            params={"is_pinned": False},
        )
        names = {item["name"] for item in r.json()["data"]}
        assert "普通会话" in names
        assert "置顶会话" not in names

        r = await client.get(
            f"/api/v1/web-apps/{token}/conversations",
            headers=headers,
            params={"is_pinned": True},
        )
        names = {item["name"] for item in r.json()["data"]}
        assert names == {"置顶会话"}

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_web_app_chat_forbidden_conversation(app, auth_token):
    """不属于当前账号的会话应返回 error 事件"""
    from app.db import AsyncSessionLocal
    from app.models.conversation import Conversation

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_id, token = await _publish_and_token(client, headers)
        other_id = uuid4()
        async with AsyncSessionLocal() as db:
            conv = Conversation(
                app_id=UUID(app_id),
                name="别人的会话",
                invoke_from=InvokeFrom.WEB_APP,
                created_by=other_id,
            )
            db.add(conv)
            await db.flush()
            conv_id = conv.id
            await db.commit()

        async with client.stream(
            "POST",
            f"/api/v1/web-apps/{token}/chat",
            headers=headers,
            json={"query": "你好", "conversation_id": str(conv_id)},
        ) as resp:
            assert resp.status_code == 200
            text = ""
            async for line in resp.aiter_lines():
                text += line + "\n"
            assert "event: error" in text
            assert "会话不存在" in text or "forbidden" in text

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_web_app_chat_sse(app, auth_token):
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("未设置 OPENAI_API_KEY，跳过 SSE 流式联调")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        app_id, token = await _publish_and_token(client, headers)
        async with client.stream(
            "POST",
            f"/api/v1/web-apps/{token}/chat",
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
            assert received >= 1
        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
