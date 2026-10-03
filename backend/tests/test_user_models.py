#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用户模型目录：CRUD、默认、探测、删除引用校验。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "user-models@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "用户模型测试账号"

CHAT_PAYLOAD = {
    "name": "测试对话模型",
    "model_type": "chat",
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-test-key",
    "model_serve_name": "demo-chat",
    "context_window": 128000,
    "features": ["tool_call"],
    "is_default": True,
    "verify": False,
}

EMBED_PAYLOAD = {
    "name": "测试向量模型",
    "model_type": "embedding",
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-embed-key",
    "model_serve_name": "demo-embed",
    "dimension": 1536,
    "is_default": True,
    "verify": False,
}


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过用户模型测试: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过用户模型测试: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过用户模型测试: {e}")
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


@pytest.mark.asyncio
async def test_user_models_crud_default_and_key_hidden(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = dict(CHAT_PAYLOAD)
        payload["name"] = f"CRUD对话-{uuid4().hex[:8]}"
        r = await client.post("/api/v1/user-models", headers=headers, json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        chat = body["data"]
        assert chat["is_default"] is True
        assert "api_key" not in chat
        assert chat["has_api_key"] is True
        chat_id = chat["id"]

        embed_payload = dict(EMBED_PAYLOAD)
        embed_payload["name"] = f"CRUD向量-{uuid4().hex[:8]}"
        r = await client.post("/api/v1/user-models", headers=headers, json=embed_payload)
        assert r.json()["code"] == "success", r.text
        embed = r.json()["data"]
        assert embed["dimension"] == 1536
        assert embed["is_default"] is True
        embed_id = embed["id"]

        r = await client.get("/api/v1/user-models", headers=headers, params={"model_type": "chat"})
        assert r.json()["code"] == "success"
        chats = r.json()["data"]
        assert any(item["id"] == chat_id for item in chats)
        assert all("api_key" not in item for item in chats)

        r = await client.post(
            f"/api/v1/user-models/{chat_id}",
            headers=headers,
            json={"name": "改名对话模型", "api_key": ""},
        )
        assert r.json()["code"] == "success"
        assert r.json()["data"]["name"] == "改名对话模型"
        assert r.json()["data"]["has_api_key"] is True

        second_chat = dict(CHAT_PAYLOAD)
        second_chat["name"] = f"第二个对话模型-{uuid4().hex[:8]}"
        second_chat["model_serve_name"] = "demo-chat-2"
        second_chat["is_default"] = False
        r = await client.post("/api/v1/user-models", headers=headers, json=second_chat)
        second_id = r.json()["data"]["id"]
        assert r.json()["data"]["is_default"] is False

        r = await client.post(f"/api/v1/user-models/{second_id}/default", headers=headers)
        assert r.json()["data"]["is_default"] is True
        r = await client.get("/api/v1/user-models", headers=headers, params={"model_type": "chat"})
        defaults = [item for item in r.json()["data"] if item["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["id"] == second_id

        r = await client.post(f"/api/v1/user-models/{second_id}/delete", headers=headers)
        assert r.json()["code"] == "success"
        r = await client.post(f"/api/v1/user-models/{chat_id}/delete", headers=headers)
        assert r.json()["code"] == "success"
        r = await client.post(f"/api/v1/user-models/{embed_id}/delete", headers=headers)
        assert r.json()["code"] == "success"


@pytest.mark.asyncio
async def test_user_models_embedding_dimension_required(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = dict(EMBED_PAYLOAD)
        payload.pop("dimension")
        payload["name"] = f"无维度-{uuid4()}"
        r = await client.post("/api/v1/user-models", headers=headers, json=payload)
        assert r.json()["code"] == "validate_error"


@pytest.mark.asyncio
async def test_user_models_probe_mocked(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"id": "demo-chat"}, {"id": "demo-embed"}]}
    mock_resp.raise_for_status.return_value = None
    with patch("app.services.user_model_service.requests.get", return_value=mock_resp):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/user-models/probe",
                headers=headers,
                json={"base_url": "https://api.example.com/v1", "api_key": "sk-test"},
            )
    assert r.status_code == 200, r.text
    assert r.json()["code"] == "success"
    ids = [item["id"] for item in r.json()["data"]["models"]]
    assert ids == ["demo-chat", "demo-embed"]


@pytest.mark.asyncio
async def test_user_models_account_isolation(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    other_email = f"user-models-other-{uuid4().hex[:8]}@test.local"
    async with AsyncSessionLocal() as db:
        other = await AccountService.ensure_account(
            email=other_email,
            password=TEST_PASSWORD,
            name=f"隔离账号-{uuid4().hex[:8]}",
            db=db,
        )
        hashed, salt = AccountService._encode_password(TEST_PASSWORD)
        other.password = hashed
        other.password_salt = salt
        await db.commit()
        other_token = create_access_token(other.id)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = dict(CHAT_PAYLOAD)
        payload["name"] = f"隔离对话-{uuid4()}"
        r = await client.post("/api/v1/user-models", headers=headers, json=payload)
        model_id = r.json()["data"]["id"]

        r = await client.get("/api/v1/user-models", headers=other_headers)
        assert all(item["id"] != model_id for item in r.json()["data"])

        r = await client.post(
            f"/api/v1/user-models/{model_id}/delete",
            headers=other_headers,
        )
        assert r.json()["code"] == "not_found"

        await client.post(f"/api/v1/user-models/{model_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_delete_chat_model_rejected_when_app_references(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = dict(CHAT_PAYLOAD)
        payload["name"] = f"引用对话-{uuid4()}"
        r = await client.post("/api/v1/user-models", headers=headers, json=payload)
        model_id = r.json()["data"]["id"]

        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={"name": f"引用应用-{uuid4().hex[:6]}", "icon": "https://example.com/icon.png", "description": ""},
        )
        app_id = r.json()["data"]["id"]
        r = await client.post(
            f"/api/v1/apps/{app_id}/draft-app-config",
            headers=headers,
            json={"model_config": {"user_model_id": model_id, "parameters": {"temperature": 0.5}}},
        )
        assert r.json()["code"] == "success", r.text

        r = await client.post(f"/api/v1/user-models/{model_id}/delete", headers=headers)
        assert r.json()["code"] == "fail"

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
        r = await client.post(f"/api/v1/user-models/{model_id}/delete", headers=headers)
        assert r.json()["code"] == "success"


@pytest.mark.asyncio
async def test_delete_embedding_model_rejected_when_dataset_references(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = dict(EMBED_PAYLOAD)
        payload["name"] = f"引用向量-{uuid4()}"
        r = await client.post("/api/v1/user-models", headers=headers, json=payload)
        model_id = r.json()["data"]["id"]

        r = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": f"引用知识库-{uuid4().hex[:6]}",
                "icon": "https://example.com/icon.png",
                "description": "",
                "embedding_model_id": model_id,
            },
        )
        assert r.json()["code"] == "success", r.text
        r = await client.get("/api/v1/datasets", headers=headers)
        dataset_id = r.json()["data"]["list"][0]["id"]

        r = await client.post(f"/api/v1/user-models/{model_id}/delete", headers=headers)
        assert r.json()["code"] == "fail"

        await client.post(f"/api/v1/datasets/{dataset_id}/delete", headers=headers)
        r = await client.post(f"/api/v1/user-models/{model_id}/delete", headers=headers)
        assert r.json()["code"] == "success"
