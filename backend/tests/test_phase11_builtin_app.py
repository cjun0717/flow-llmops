#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 11.2：应用广场冒烟测试。

不依赖 Docker 的用例会实际跑通（yaml 加载、列表映射、不存在模板）。
需要数据库的联调用例在 DB 不可用时 skip。
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.builtin_apps import BuiltinAppManager
from app.exceptions import NotFoundException
from app.main import create_app
from app.schemas.builtin_app import AddBuiltinAppToSpaceReq, GetBuiltinAppsResp
from app.services.builtin_app_service import BuiltinAppService


PRODUCT_MANAGER_ID = "6b476bc2-fb11-4ff7-a24e-ae8ec30605f5"
TRAVEL_ASSISTANT_ID = "d3296faf-6ad7-4475-ac95-53308496e377"


@pytest.fixture(scope="module")
def manager() -> BuiltinAppManager:
    return BuiltinAppManager()


def test_load_categories(manager: BuiltinAppManager):
    categories = manager.get_categories()
    assert len(categories) == 4
    mapping = {item.category: item.name for item in categories}
    assert mapping["assistant"] == "助手"
    assert mapping["hr"] == "人力资源"
    assert mapping["writing"] == "写作"
    assert mapping["ecommerce"] == "电商营销"


def test_load_builtin_apps(manager: BuiltinAppManager):
    apps = manager.get_builtin_apps()
    ids = {item.id for item in apps}
    assert PRODUCT_MANAGER_ID in ids
    assert TRAVEL_ASSISTANT_ID in ids
    assert len(apps) == 2


def test_get_builtin_app_by_id(manager: BuiltinAppManager):
    app = manager.get_builtin_app(PRODUCT_MANAGER_ID)
    assert app is not None
    assert app.name == "LLM应用产品经理"
    assert app.category == "assistant"
    assert app.language_model_config["provider"] == "openai"
    assert app.language_model_config["model"] == "gpt-4o-mini"
    assert app.long_term_memory["enable"] is True
    assert app.tools[0]["provider_id"] == "google"
    assert app.tools[0]["tool_id"] == "google_serper"


def test_get_builtin_app_missing(manager: BuiltinAppManager):
    assert manager.get_builtin_app(str(uuid4())) is None


def test_list_resp_only_exposes_provider_and_model(manager: BuiltinAppManager):
    """列表接口只返回 provider/model，不把完整 parameters 暴露给前端"""
    entity = manager.get_builtin_app(TRAVEL_ASSISTANT_ID)
    resp = GetBuiltinAppsResp.from_entity(entity)
    dumped = resp.model_dump(by_alias=True)
    assert dumped["model_config"] == {"provider": "openai", "model": "gpt-4o-mini"}
    assert "parameters" not in dumped["model_config"]
    assert dumped["name"] == "旅游助手"


def test_add_builtin_app_req_invalid_uuid():
    with pytest.raises(ValidationError):
        AddBuiltinAppToSpaceReq(builtin_app_id="not-a-uuid")


@pytest.mark.asyncio
async def test_add_builtin_app_not_found(manager: BuiltinAppManager):
    account = type("Account", (), {"id": uuid4()})()
    with pytest.raises(NotFoundException) as exc:
        await BuiltinAppService.add_builtin_app_to_space(uuid4(), account, None, manager)
    assert "不存在" in exc.value.message


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
        pytest.skip(f"数据库不可用，跳过阶段11.2联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段11.2联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段11.2联调: {e}")
        raise

    async with AsyncSessionLocal() as db:
        account = await AccountService.ensure_account(
            email="phase11-builtin-app@test.local",
            password="Test1234",
            name="阶段11.2测试账号",
            db=db,
        )
        password_hashed, password_salt = AccountService._encode_password("Test1234")
        account.password = password_hashed
        account.password_salt = password_salt
        account.name = "阶段11.2测试账号"
        await db.commit()

    return create_access_token(account.id)


@pytest.mark.asyncio
async def test_builtin_apps_http_list(app, auth_token):
    """登录后获取分类与应用列表"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/builtin-apps/categories", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        categories = {item["category"]: item["name"] for item in body["data"]}
        assert categories["assistant"] == "助手"
        assert len(body["data"]) == 4

        r = await client.get("/api/v1/builtin-apps", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        apps = body["data"]
        assert len(apps) == 2
        names = {item["name"] for item in apps}
        assert "LLM应用产品经理" in names
        assert "旅游助手" in names
        for item in apps:
            assert set(item["model_config"].keys()) == {"provider", "model"}


@pytest.mark.asyncio
async def test_add_builtin_app_http_not_found(app, auth_token):
    """登录后添加不存在的内置应用应 not_found"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/builtin-apps/add-builtin-app-to-space",
            headers=headers,
            json={"builtin_app_id": str(uuid4())},
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "not_found"


@pytest.mark.asyncio
async def test_add_builtin_app_http_success(app, auth_token):
    """登录后将内置应用加入空间，返回新应用 id"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/builtin-apps/add-builtin-app-to-space",
            headers=headers,
            json={"builtin_app_id": PRODUCT_MANAGER_ID},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        app_id = body["data"]["id"]
        UUID(app_id)

        detail = await client.get(f"/api/v1/apps/{app_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["data"]["name"] == "LLM应用产品经理"

        draft = await client.get(f"/api/v1/apps/{app_id}/draft-app-config", headers=headers)
        assert draft.status_code == 200
        draft_data = draft.json()["data"]
        assert draft_data["model_config"]["provider"] == "openai"
        assert draft_data["long_term_memory"]["enable"] is True
        assert draft_data["opening_statement"].startswith("我是一个高级产品经理")

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
