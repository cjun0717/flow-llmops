#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 10：开放 API（ApiKey 鉴权）冒烟测试。

测试 API 秘钥 CRUD + ApiKey 鉴权访问开放 Chat 接口的鉴权链路。
注意：真实 Chat 对话依赖 LLM/工具调用，无凭证时跳过；鉴权失败用例不依赖外部服务。
Docker 服务停止时整体跳过。
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.models.account import Account
from app.models.api_key import ApiKey
from app.services.account_service import AccountService
from app.services.api_key_service import ApiKeyService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase10@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段10测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段10联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段10联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段10联调: {e}")
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


async def _get_account_id():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Account).where(Account.email == TEST_EMAIL))
        account = result.scalar_one()
        return account.id


@pytest.mark.asyncio
async def test_phase10_api_key_crud(app, auth_token):
    """API 秘钥 CRUD 完整流程：创建→列表→更新→切换激活→删除"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建秘钥
        r = await client.post(
            "/api/v1/openapi/api-keys",
            headers=headers,
            json={"is_active": True, "remark": "阶段10测试秘钥"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success"

        # 2. 列表
        r = await client.get("/api/v1/openapi/api-keys", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        assert body["data"]["paginator"]["total_record"] >= 1
        items = body["data"]["list"]
        api_key_id = items[0]["id"]
        assert items[0]["api_key"].startswith("llmops-v1/")
        assert items[0]["is_active"] is True

        # 3. 更新秘钥备注
        r = await client.post(
            f"/api/v1/openapi/api-keys/{api_key_id}",
            headers=headers,
            json={"is_active": True, "remark": "阶段10改备注"},
        )
        assert r.status_code == 200, r.text
        r = await client.get("/api/v1/openapi/api-keys", headers=headers)
        item = next(it for it in r.json()["data"]["list"] if it["id"] == api_key_id)
        assert item["remark"] == "阶段10改备注"

        # 4. 切换激活状态
        r = await client.post(
            f"/api/v1/openapi/api-keys/{api_key_id}/is-active",
            headers=headers,
            json={"is_active": False},
        )
        assert r.status_code == 200, r.text
        r = await client.get("/api/v1/openapi/api-keys", headers=headers)
        item = next(it for it in r.json()["data"]["list"] if it["id"] == api_key_id)
        assert item["is_active"] is False

        # 5. 删除
        r = await client.post(
            f"/api/v1/openapi/api-keys/{api_key_id}/delete", headers=headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success"


@pytest.mark.asyncio
async def test_phase10_openapi_chat_auth(app, auth_token):
    """开放 Chat 接口鉴权：无凭证/无效凭证/未激活秘钥应拒绝"""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 无 Authorization 头应 401
        r = await client.post(
            "/api/v1/openapi/chat",
            json={"app_id": "00000000-0000-0000-0000-000000000000", "query": "你好"},
        )
        body = r.json()
        assert body["code"] == "unauthorized"

        # 2. 无效 api_key 应 401
        r = await client.post(
            "/api/v1/openapi/chat",
            headers={"Authorization": "Bearer llmops-v1/invalid_key"},
            json={"app_id": "00000000-0000-0000-0000-000000000000", "query": "你好"},
        )
        body = r.json()
        assert body["code"] == "unauthorized"

        # 3. 未激活秘钥应 401
        account_id = await _get_account_id()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Account).where(Account.id == account_id))
            account = result.scalar_one()
            api_key = ApiKey(
                account_id=account.id,
                api_key=ApiKeyService.generate_api_key(),
                is_active=False,
                remark="未激活秘钥",
            )
            db.add(api_key)
            await db.commit()
            await db.refresh(api_key)
            inactive_key = api_key.api_key

        r = await client.post(
            "/api/v1/openapi/chat",
            headers={"Authorization": f"Bearer {inactive_key}"},
            json={"app_id": "00000000-0000-0000-0000-000000000000", "query": "你好"},
        )
        body = r.json()
        assert body["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_phase10_openapi_chat_request_validation(app, auth_token):
    """开放 Chat 接口请求校验：query 为空、image_urls 超过5条、conversation_id 非UUID 应失败"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建一个激活的 api_key 用于通过鉴权（请求校验在鉴权后）
        account_id = await _get_account_id()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Account).where(Account.id == account_id))
            account = result.scalar_one()
            api_key = ApiKey(
                account_id=account.id,
                api_key=ApiKeyService.generate_api_key(),
                is_active=True,
                remark="阶段10激活秘钥",
            )
            db.add(api_key)
            await db.commit()
            await db.refresh(api_key)
            active_key = api_key.api_key
            api_key_id = api_key.id

        key_headers = {"Authorization": f"Bearer {active_key}"}

        # 2. query 为空 -> 校验失败
        r = await client.post(
            "/api/v1/openapi/chat",
            headers=key_headers,
            json={"app_id": "00000000-0000-0000-0000-000000000000", "query": ""},
        )
        assert r.status_code == 422

        # 3. image_urls 超过5条 -> 校验失败
        r = await client.post(
            "/api/v1/openapi/chat",
            headers=key_headers,
            json={
                "app_id": "00000000-0000-0000-0000-000000000000",
                "query": "你好",
                "image_urls": [f"https://example.com/{i}.png" for i in range(6)],
            },
        )
        assert r.status_code == 422

        # 4. conversation_id 非UUID -> 校验失败
        r = await client.post(
            "/api/v1/openapi/chat",
            headers=key_headers,
            json={
                "app_id": "00000000-0000-0000-0000-000000000000",
                "query": "你好",
                "conversation_id": "not-a-uuid",
            },
        )
        assert r.status_code == 422

        # 5. 清理
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ApiKey).where(ApiKey.id == api_key_id))
            ak = result.scalar_one()
            await db.delete(ak)
            await db.commit()
