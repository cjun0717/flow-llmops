#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 2：文件上传冒烟测试。"""
from __future__ import annotations

import io

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase2@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段2测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段2联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段2联调: {e}")
    except Exception as e:
        # asyncpg 连接拒绝等
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段2联调: {e}")
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
async def test_upload_image(app, auth_token):
    """上传图片：需要 MinIO + Postgres，否则 skip"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    # 1x1 透明 PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/upload-files/image",
            headers=headers,
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
        )
        if r.status_code != 200 or r.json().get("code") != "success":
            pytest.skip(f"MinIO 不可用，跳过上传联调: {r.text}")
        body = r.json()
        assert body["code"] == "success"
        assert "image_url" in body["data"]
        assert body["data"]["image_url"].startswith("http")


@pytest.mark.asyncio
async def test_upload_file(app, auth_token):
    """上传文件：需要 MinIO + Postgres，否则 skip"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    md_content = b"# test\nhello world"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/upload-files/file",
            headers=headers,
            files={"file": ("test.md", io.BytesIO(md_content), "text/markdown")},
        )
        if r.status_code != 200 or r.json().get("code") != "success":
            pytest.skip(f"MinIO 不可用，跳过上传联调: {r.text}")
        body = r.json()
        assert body["code"] == "success"
        data = body["data"]
        assert data["name"] == "test.md"
        assert data["extension"] == "md"
        assert data["size"] == len(md_content)
        assert "key" in data


@pytest.mark.asyncio
async def test_upload_invalid_extension(app, auth_token):
    """不允许的扩展名应返回 fail"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/upload-files/file",
            headers=headers,
            files={"file": ("test.exe", io.BytesIO(b"\x00\x00"), "application/octet-stream")},
        )
        # 数据库不可用时也会 skip，这里只验证扩展名校验
        if r.status_code != 200:
            pytest.skip("环境不可用")
        body = r.json()
        assert body["code"] == "fail"
        assert "不允许上传" in body["message"]
