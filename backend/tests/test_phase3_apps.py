#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 3：应用 CRUD 冒烟测试。"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase3@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段3测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段3联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段3联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段3联调: {e}")
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

    token = create_access_token(account.id)
    return token


@pytest.mark.asyncio
async def test_phase3_app_crud_flow(app, auth_token):
    """应用 CRUD 完整流程：创建→列表→详情→改名→复制→删除"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建应用
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={
                "name": "测试应用",
                "icon": "https://example.com/icon.png",
                "description": "阶段3测试",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        app_id = body["data"]["id"]

        # 2. 列表查询
        r = await client.get("/api/v1/apps", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        assert len(body["data"]["list"]) >= 1
        item = body["data"]["list"][0]
        assert item["name"] == "测试应用"
        assert "preset_prompt" in item
        assert "model_config" in item

        # 3. 搜索
        r = await client.get(
            "/api/v1/apps", headers=headers, params={"search_word": "测试"}
        )
        assert r.status_code == 200
        assert len(r.json()["data"]["list"]) >= 1

        r = await client.get(
            "/api/v1/apps", headers=headers, params={"search_word": "不存在"}
        )
        assert r.status_code == 200
        assert len(r.json()["data"]["list"]) == 0

        # 4. 详情
        r = await client.get(f"/api/v1/apps/{app_id}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        assert body["data"]["name"] == "测试应用"
        assert body["data"]["status"] == "draft"
        assert body["data"]["draft_updated_at"] > 0

        # 5. 改名
        r = await client.post(
            f"/api/v1/apps/{app_id}",
            headers=headers,
            json={
                "name": "改名后应用",
                "icon": "https://example.com/icon2.png",
                "description": "已修改",
            },
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        r = await client.get(f"/api/v1/apps/{app_id}", headers=headers)
        assert r.json()["data"]["name"] == "改名后应用"
        assert r.json()["data"]["description"] == "已修改"

        # 6. 复制
        r = await client.post(f"/api/v1/apps/{app_id}/copy", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        copied_id = body["data"]["id"]
        assert copied_id != app_id

        r = await client.get(f"/api/v1/apps/{copied_id}", headers=headers)
        assert r.json()["data"]["name"] == "改名后应用"

        # 7. 删除原应用
        r = await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        # 8. 删除后查不到
        r = await client.get(f"/api/v1/apps/{app_id}", headers=headers)
        assert r.json()["code"] == "not_found"

        # 9. 清理复制的应用
        r = await client.post(f"/api/v1/apps/{copied_id}/delete", headers=headers)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_phase3_app_forbidden(app, auth_token):
    """无权限访问他人应用"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 用一个不存在的 UUID 查询
        r = await client.get(
            "/api/v1/apps/00000000-0000-0000-0000-000000000001",
            headers=headers,
        )
        assert r.json()["code"] == "not_found"
