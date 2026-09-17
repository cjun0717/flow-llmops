#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 1：授权认证 + 账号设置冒烟测试。"""
from __future__ import annotations

import base64
import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token, parse_access_token
from app.utils.password import compare_password, hash_password

TEST_EMAIL = "phase1@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段1测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def seeded_account():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段1联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段1联调: {e}")
    except Exception as e:
        # asyncpg 连接拒绝等
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段1联调: {e}")
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
        await db.refresh(account)
        return account


@pytest.mark.asyncio
async def test_password_hash_roundtrip():
    salt = secrets.token_bytes(16)
    hashed = hash_password(TEST_PASSWORD, salt)
    assert compare_password(
        TEST_PASSWORD,
        base64.b64encode(hashed).decode(),
        base64.b64encode(salt).decode(),
    )


@pytest.mark.asyncio
async def test_jwt_roundtrip():
    token = create_access_token("00000000-0000-0000-0000-000000000001")
    payload = parse_access_token(token)
    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert payload["iss"] == "llmops"


@pytest.mark.asyncio
async def test_phase1_auth_account_flow(app, seeded_account):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/oauth/github")
        assert r.status_code == 200
        assert r.json()["code"] == "fail"

        r = await client.post(
            "/api/v1/auth/password-login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "success"
        token = body["data"]["access_token"]
        assert body["data"]["expire_at"] > 0

        headers = {"Authorization": f"Bearer {token}"}

        r = await client.get("/api/v1/account", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "success"
        assert body["data"]["email"] == TEST_EMAIL

        r = await client.post(
            "/api/v1/account/name",
            headers=headers,
            json={"name": "改名后账号"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        r = await client.get("/api/v1/account", headers=headers)
        assert r.json()["data"]["name"] == "改名后账号"

        r = await client.post(
            "/api/v1/account/avatar",
            headers=headers,
            json={"avatar": "https://example.com/a.png"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        new_password = "Test5678"
        r = await client.post(
            "/api/v1/account/password",
            headers=headers,
            json={"password": new_password},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        r = await client.post(
            "/api/v1/auth/password-login",
            json={"email": TEST_EMAIL, "password": new_password},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"
        token2 = r.json()["data"]["access_token"]

        r = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

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
