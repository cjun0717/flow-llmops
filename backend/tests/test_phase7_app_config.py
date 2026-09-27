#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 7：应用配置与发布冒烟测试。"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase7@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段7测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段7联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段7联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段7联调: {e}")
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
async def test_phase7_app_config_flow(app, auth_token):
    """应用配置与发布完整流程：草稿读取→更新→发布→published_config→token→历史→回退→取消"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建应用
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={
                "name": "阶段7应用",
                "icon": "https://example.com/icon.png",
                "description": "阶段7测试",
            },
        )
        assert r.status_code == 200, r.text
        app_id = r.json()["data"]["id"]

        # 2. 读取草稿配置（默认配置）
        r = await client.get(f"/api/v1/apps/{app_id}/draft-app-config", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        draft = body["data"]
        assert draft["model_config"]["provider"] == "openai"
        assert draft["model_config"]["model"] == "gpt-4o-mini"
        assert draft["dialog_round"] == 3
        assert draft["opening_statement"] == ""
        assert draft["tools"] == []
        assert draft["workflows"] == []
        assert draft["datasets"] == []

        # 3. 更新草稿配置（简单字段：preset_prompt + dialog_round + opening_statement）
        r = await client.post(
            f"/api/v1/apps/{app_id}/draft-app-config",
            headers=headers,
            json={
                "preset_prompt": "你是一个有用的助手",
                "dialog_round": 5,
                "opening_statement": "你好，请问有什么可以帮你？",
                "opening_questions": ["今天天气怎么样？", "讲个笑话"],
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success", r.json()

        # 4. 再次读取草稿配置，确认更新生效
        r = await client.get(f"/api/v1/apps/{app_id}/draft-app-config", headers=headers)
        assert r.status_code == 200
        draft = r.json()["data"]
        assert draft["preset_prompt"] == "你是一个有用的助手"
        assert draft["dialog_round"] == 5
        assert draft["opening_statement"] == "你好，请问有什么可以帮你？"
        assert len(draft["opening_questions"]) == 2

        # 5. 发布应用
        r = await client.post(f"/api/v1/apps/{app_id}/publish", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success", r.json()

        # 6. 读取已发布配置
        r = await client.get(f"/api/v1/apps/{app_id}/published-config", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        web_app = body["data"]["web_app"]
        assert web_app["status"] == "published"
        assert "token" in web_app

        # 7. 重新生成 WebApp token
        r = await client.post(
            f"/api/v1/apps/{app_id}/published-config/regenerate-web-app-token",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success"
        new_token = r.json()["data"]["token"]
        assert new_token

        # 8. 获取发布历史
        r = await client.get(
            f"/api/v1/apps/{app_id}/publish-histories", headers=headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        assert body["data"]["paginator"]["total_record"] >= 1
        history_items = body["data"]["list"]
        assert len(history_items) >= 1
        history_id = history_items[0]["id"]
        assert history_items[0]["version"] == 1

        # 9. 回退历史版本到草稿
        r = await client.post(
            f"/api/v1/apps/{app_id}/fallback-history",
            headers=headers,
            json={"app_config_version_id": history_id},
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success", r.json()

        # 10. 读取草稿配置，确认回退后内容与发布时一致
        r = await client.get(f"/api/v1/apps/{app_id}/draft-app-config", headers=headers)
        assert r.status_code == 200
        draft = r.json()["data"]
        assert draft["preset_prompt"] == "你是一个有用的助手"
        assert draft["dialog_round"] == 5

        # 11. 取消发布
        r = await client.post(f"/api/v1/apps/{app_id}/cancel-publish", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success", r.json()

        # 12. 取消后 published-config 的 status 应为 draft
        r = await client.get(f"/api/v1/apps/{app_id}/published-config", headers=headers)
        assert r.status_code == 200
        assert r.json()["data"]["web_app"]["status"] == "draft"

        # 13. 取消发布后无法再生成 token
        r = await client.post(
            f"/api/v1/apps/{app_id}/published-config/regenerate-web-app-token",
            headers=headers,
        )
        assert r.json()["code"] == "fail"

        # 14. 清理：删除应用
        r = await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == "success"


@pytest.mark.asyncio
async def test_phase7_update_draft_validate_error(app, auth_token):
    """更新草稿配置时校验失败返回 validate_error"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 创建应用
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={
                "name": "阶段7校验应用",
                "icon": "https://example.com/icon.png",
                "description": "校验测试",
            },
        )
        app_id = r.json()["data"]["id"]

        # dialog_round 超范围
        r = await client.post(
            f"/api/v1/apps/{app_id}/draft-app-config",
            headers=headers,
            json={"dialog_round": 999},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "validate_error", r.json()

        # model_config 缺少字段
        r = await client.post(
            f"/api/v1/apps/{app_id}/draft-app-config",
            headers=headers,
            json={"model_config": {"provider": "openai"}},
        )
        assert r.json()["code"] == "validate_error"

        # 不存在的 provider
        r = await client.post(
            f"/api/v1/apps/{app_id}/draft-app-config",
            headers=headers,
            json={
                "model_config": {
                    "provider": "not_exist_provider",
                    "model": "xxx",
                    "parameters": {},
                }
            },
        )
        assert r.json()["code"] == "validate_error"

        # 清理
        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_phase7_publish_histories_pagination(app, auth_token):
    """发布历史分页参数校验"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={
                "name": "阶段7分页应用",
                "icon": "https://example.com/icon.png",
                "description": "分页测试",
            },
        )
        app_id = r.json()["data"]["id"]

        # 发布一次以产生历史
        await client.post(f"/api/v1/apps/{app_id}/publish", headers=headers)

        # 默认分页
        r = await client.get(
            f"/api/v1/apps/{app_id}/publish-histories", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["data"]["paginator"]["current_page"] == 1
        assert r.json()["data"]["paginator"]["page_size"] == 20

        # 自定义分页
        r = await client.get(
            f"/api/v1/apps/{app_id}/publish-histories",
            headers=headers,
            params={"current_page": 1, "page_size": 10},
        )
        assert r.status_code == 200
        assert r.json()["data"]["paginator"]["page_size"] == 10

        # 清理
        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
