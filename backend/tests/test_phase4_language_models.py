#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 4：语言模型只读冒烟测试。"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase4@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段4测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    """登录令牌（需数据库可用，否则跳过需登录的测试）"""
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段4需登录测试: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段4需登录测试: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段4需登录测试: {e}")
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
async def test_get_language_models_placeholder():
    """占位（实际列表测试见 test_get_language_models_with_auth）"""
    pass


@pytest.mark.asyncio
async def test_get_language_models_with_auth(app, auth_token):
    """GET /language-models 需登录，返回提供商列表"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/language-models", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        providers = body["data"]
        assert isinstance(providers, list)
        assert len(providers) >= 6
        names = [p["name"] for p in providers]
        assert "openai" in names
        assert "moonshot" in names
        assert "tongyi" in names
        assert "ollama" in names
        assert "deepseek" in names
        assert "wenxin_v2" in names

        openai = next(p for p in providers if p["name"] == "openai")
        assert openai["label"] == "OpenAI"
        assert openai["position"] == 1
        assert "chat" in openai["support_model_types"]
        model_names = [m["model_name"] for m in openai["models"]]
        assert "gpt-4o" in model_names
        assert "gpt-4o-mini" in model_names
        # 模型参数模板应被填充
        gpt4o_mini = next(m for m in openai["models"] if m["model_name"] == "gpt-4o-mini")
        param_names = [p["name"] for p in gpt4o_mini["parameters"]]
        assert "temperature" in param_names
        assert "max_tokens" in param_names
        temp_param = next(p for p in gpt4o_mini["parameters"] if p["name"] == "temperature")
        assert temp_param["label"] == "温度"
        assert temp_param["type"] == "float"


@pytest.mark.asyncio
async def test_get_language_model_detail(app, auth_token):
    """GET /language-models/{provider}/{model} 返回模型详情"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/language-models/openai/gpt-4o-mini", headers=headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        data = body["data"]
        assert data["model_name"] == "gpt-4o-mini"
        assert data["model_type"] == "chat"
        assert "tool_call" in data["features"]
        assert data["context_window"] == 128000
        assert data["max_output_tokens"] == 16384
        assert data["attributes"]["model"] == "gpt-4o-mini"
        assert data["metadata"]["pricing"]["input"] == 0.0011


@pytest.mark.asyncio
async def test_get_language_model_icon(app):
    """GET /language-models/{provider}/icon 公开返回图标二进制"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/language-models/openai/icon")
        assert r.status_code == 200, r.text
        assert len(r.content) > 0
        assert r.headers.get("content-type", "").startswith("image/svg")
        # 不需要 Authorization 也能访问
        r2 = await client.get("/api/v1/language-models/deepseek/icon")
        assert r2.status_code == 200
        assert len(r2.content) > 0


@pytest.mark.asyncio
async def test_get_language_model_not_found(app, auth_token):
    """GET /language-models/notexist/xxx 返回 not_found"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/language-models/notexist/xxx", headers=headers
        )
        body = r.json()
        assert body["code"] == "not_found"

        r2 = await client.get(
            "/api/v1/language-models/openai/notexist-model", headers=headers
        )
        assert r2.json()["code"] == "not_found"

        r3 = await client.get("/api/v1/language-models/notexist/icon")
        assert r3.json()["code"] == "not_found"


@pytest.mark.asyncio
async def test_get_language_models_unauthorized(app):
    """GET /language-models 未登录返回 unauthorized"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/language-models")
        body = r.json()
        assert body["code"] == "unauthorized"
