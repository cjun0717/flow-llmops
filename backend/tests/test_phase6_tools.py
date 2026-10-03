#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 6：插件（内置只读 + API Tool + MCP Tool）冒烟测试。

测试范围：
- 内置工具：get_builtin_tools / get_provider_tool / get_provider_icon / get_categories
- API Tool：validate_openapi_schema / create / list / get_provider / get_tool / update / delete
- MCP Tool：parse_mcp_schema（仅离线校验，不联网）

MCP 远程联网用例默认 skip（需真实 MCP 服务器）。
"""
from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase6@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段6测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段6联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段6联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段6联调: {e}")
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


# ===== 内置工具 =====


@pytest.mark.asyncio
async def test_get_builtin_tools(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/builtin-tools", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "success"
        data = body["data"]
        assert isinstance(data, list)
        names = {p["name"] for p in data}
        # 7 个内置提供商
        assert {"google", "time", "duckduckgo", "dalle", "gaode", "wikipedia", "pptx"} <= names


@pytest.mark.asyncio
async def test_get_provider_tool(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/builtin-tools/providers/time/tools/current_time", headers=headers
        )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "success"
        data = body["data"]
        assert data["name"] == "current_time"
        assert data["provider"]["name"] == "time"


@pytest.mark.asyncio
async def test_get_provider_icon(app):
    """icon 端点无需登录"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/builtin-tools/providers/time/icon")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/")
        assert len(r.content) > 0

        r_alias = await client.get("/api/v1/builtin-tools/time/icon")
        assert r_alias.status_code == 200
        assert r_alias.content == r.content


@pytest.mark.asyncio
async def test_get_categories(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/builtin-tools/categories", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "success"
        cats = {c["category"] for c in body["data"]}
        assert {"search", "image", "weather", "tool", "other"} <= cats


@pytest.mark.asyncio
async def test_builtin_tools_unauthorized(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/builtin-tools")
        assert r.status_code == 200
        assert r.json()["code"] == "unauthorized"


# ===== API Tool =====


VALID_OPENAPI_SCHEMA = json.dumps(
    {
        "server": "https://api.example.com",
        "description": "测试用API",
        "paths": {
            "/weather": {
                "get": {
                    "operationId": "getWeather",
                    "description": "获取天气信息",
                    "parameters": [
                        {
                            "name": "city",
                            "in": "query",
                            "description": "城市名",
                            "required": True,
                            "type": "str",
                        }
                    ],
                }
            }
        },
    },
    ensure_ascii=False,
)


@pytest.mark.asyncio
async def test_validate_openapi_schema(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/api-tools/validate-openapi-schema",
            headers=headers,
            json={
                "name": "测试",
                "icon": "https://example.com/icon.png",
                "openapi_schema": VALID_OPENAPI_SCHEMA,
                "headers": [],
            },
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"


@pytest.mark.asyncio
async def test_api_tool_crud(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1.创建
        r = await client.post(
            "/api/v1/api-tools",
            headers=headers,
            json={
                "name": "天气API",
                "icon": "https://example.com/icon.png",
                "openapi_schema": VALID_OPENAPI_SCHEMA,
                "headers": [],
            },
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        # 2.列表
        r = await client.get("/api/v1/api-tools", headers=headers)
        assert r.status_code == 200
        providers = r.json()["data"]["list"]
        assert any(p["name"] == "天气API" for p in providers)
        provider_id = providers[0]["id"]
        # 工具应被解析出来
        assert any(t["name"] == "getWeather" for t in providers[0]["tools"])

        # 3.获取 provider
        r = await client.get(f"/api/v1/api-tools/{provider_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "天气API"

        # 4.获取 tool
        r = await client.get(
            f"/api/v1/api-tools/{provider_id}/tools/getWeather", headers=headers
        )
        assert r.status_code == 200
        tool_data = r.json()["data"]
        assert tool_data["name"] == "getWeather"
        assert tool_data["provider"]["id"] == provider_id

        # 5.更新
        r = await client.post(
            f"/api/v1/api-tools/{provider_id}",
            headers=headers,
            json={
                "name": "天气APIv2",
                "icon": "https://example.com/icon2.png",
                "openapi_schema": VALID_OPENAPI_SCHEMA,
                "headers": [],
            },
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        # 6.删除
        r = await client.post(f"/api/v1/api-tools/{provider_id}/delete", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        # 7.确认删除
        r = await client.get("/api/v1/api-tools", headers=headers)
        assert not any(p["name"] == "天气APIv2" for p in r.json()["data"]["list"])


# ===== MCP Tool（仅离线 schema 校验）=====


def test_mcp_parse_schema_offline():
    """离线测试 MCP schema 解析（不联网）"""
    from app.services.mcp_tool_service import McpToolService

    service = McpToolService.__new__(McpToolService)
    schema = json.dumps(
        {
            "mcpServers": {
                "test": {
                    "transport": "http",
                    "url": "https://example.com/mcp",
                    "headers": {"Authorization": "Bearer xxx"},
                    "description": "测试MCP",
                }
            }
        },
        ensure_ascii=False,
    )
    servers = McpToolService.parse_mcp_schema(schema)
    assert len(servers) == 1
    assert servers[0]["name"] == "test"
    assert servers[0]["config"]["transport"] == "http"
    assert servers[0]["config"]["url"] == "https://example.com/mcp"


def test_mcp_parse_schema_reject_stdio():
    """stdio 传输应被拒绝"""
    from app.exceptions import ValidateException
    from app.services.mcp_tool_service import McpToolService

    schema = json.dumps(
        {
            "mcpServers": {
                "local": {
                    "command": "npx",
                    "args": ["-y", "some-mcp"],
                }
            }
        },
        ensure_ascii=False,
    )
    with pytest.raises(ValidateException):
        McpToolService.parse_mcp_schema(schema)


def test_mcp_parse_schema_empty():
    """空 mcpServers 应被拒绝"""
    from app.exceptions import ValidateException
    from app.services.mcp_tool_service import McpToolService

    with pytest.raises(ValidateException):
        McpToolService.parse_mcp_schema(json.dumps({"mcpServers": {}}))


def test_mcp_parse_schema_disabled_skipped():
    """disabled=true 的服务器应被跳过"""
    from app.exceptions import ValidateException
    from app.services.mcp_tool_service import McpToolService

    schema = json.dumps(
        {
            "mcpServers": {
                "off": {
                    "transport": "http",
                    "url": "https://example.com/mcp",
                    "disabled": True,
                }
            }
        },
        ensure_ascii=False,
    )
    with pytest.raises(ValidateException):
        McpToolService.parse_mcp_schema(schema)
