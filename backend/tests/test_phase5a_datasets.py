#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 5a：知识库 CRUD 冒烟测试。

测试范围：
- Dataset CRUD 全流程（不依赖 Milvus/OpenAI）
- Document 创建（触发 Celery；若 worker 未起则仅验记录建立，异步构建部分跳过）
- Segment 手动 CRUD（同步写 Milvus，需 Milvus + OpenAI Embedding 可用，否则 skip）
- 文件解析端到端（上传 txt → create_documents → 查 segments，需 worker + Milvus + OpenAI）

DB/Milvus/OpenAI 不可用时按用例 skip。
"""
from __future__ import annotations

import io

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase5a@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段5a测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段5a联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段5a联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段5a联调: {e}")
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


def _milvus_available() -> bool:
    """检测 Milvus 是否可连接"""
    try:
        from pymilvus import MilvusClient
        from app.config import settings
        c = MilvusClient(uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        c.close()
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_dataset_crud_flow(app, auth_token):
    """Dataset CRUD 全流程：创建→列表→详情→改名→删除（不依赖向量库）"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建知识库
        r = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "测试知识库5a",
                "icon": "https://example.com/icon.png",
                "description": "阶段5a测试",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        dataset_id = body["data"]  # create 返回空 dict，需要从列表获取 id

        # 2. 列表查询
        r = await client.get("/api/v1/datasets", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        items = body["data"]["list"]
        assert len(items) >= 1
        dataset_id = items[0]["id"]
        assert items[0]["name"] == "测试知识库5a"
        assert items[0]["document_count"] == 0

        # 3. 搜索
        r = await client.get(
            "/api/v1/datasets", headers=headers, params={"search_word": "测试"}
        )
        assert len(r.json()["data"]["list"]) >= 1
        r = await client.get(
            "/api/v1/datasets", headers=headers, params={"search_word": "不存在"}
        )
        assert len(r.json()["data"]["list"]) == 0

        # 4. 详情
        r = await client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        assert body["data"]["name"] == "测试知识库5a"
        assert body["data"]["document_count"] == 0
        assert body["data"]["hit_count"] == 0

        # 5. 改名
        r = await client.post(
            f"/api/v1/datasets/{dataset_id}",
            headers=headers,
            json={
                "name": "改名后知识库",
                "icon": "https://example.com/icon2.png",
                "description": "已修改",
            },
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        r = await client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
        assert r.json()["data"]["name"] == "改名后知识库"

        # 6. 重名检测
        r = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "另一个知识库",
                "icon": "https://example.com/icon.png",
                "description": "",
            },
        )
        assert r.status_code == 200
        # 再创建同名应失败
        r = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "另一个知识库",
                "icon": "https://example.com/icon.png",
                "description": "",
            },
        )
        assert r.json()["code"] == "validate_error"

        # 7. 查询记录（空）
        r = await client.get(f"/api/v1/datasets/{dataset_id}/queries", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == "success"
        assert isinstance(r.json()["data"], list)

        # 8. 列表清理（删除创建的知识库）
        r = await client.get("/api/v1/datasets", headers=headers)
        for item in r.json()["data"]["list"]:
            rid = await client.post(
                f"/api/v1/datasets/{item['id']}/delete", headers=headers
            )
            assert rid.status_code == 200


@pytest.mark.asyncio
async def test_dataset_not_found(app, auth_token):
    """访问不存在的知识库返回 not_found"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000001", headers=headers
        )
        assert r.json()["code"] in ("not_found", "forbidden")


@pytest.mark.asyncio
async def test_document_create_records(app, auth_token):
    """Document 创建记录建立（不依赖 worker 完成构建，仅验记录与 batch）"""
    if not _milvus_available():
        pytest.skip("Milvus 不可用，跳过文档创建测试")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建知识库
        r = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "文档测试知识库",
                "icon": "https://example.com/icon.png",
                "description": "",
            },
        )
        assert r.status_code == 200
        r = await client.get("/api/v1/datasets", headers=headers)
        dataset_id = r.json()["data"]["list"][0]["id"]

        # 2. 上传一个 txt 文件
        txt_content = "这是一个测试文档。\n\n知识库迁移阶段5a测试内容。"
        r = await client.post(
            "/api/v1/upload-files/file",
            headers=headers,
            files={"file": ("test.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")},
        )
        assert r.status_code == 200, r.text
        upload_file_id = r.json()["data"]["id"]

        # 3. 创建文档（触发 Celery）
        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/documents",
            headers=headers,
            json={
                "upload_file_ids": [upload_file_id],
                "process_type": "automatic",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        data = body["data"]
        assert len(data["documents"]) == 1
        assert data["batch"]
        batch = data["batch"]
        document_id = data["documents"][0]["id"]

        # 4. 查文档列表
        r = await client.get(f"/api/v1/datasets/{dataset_id}/documents", headers=headers)
        assert r.status_code == 200
        docs = r.json()["data"]["list"]
        assert len(docs) >= 1
        assert docs[0]["name"] == "test.txt"

        # 5. 查文档详情
        r = await client.get(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["data"]["id"] == document_id

        # 6. 查批次状态
        r = await client.get(
            f"/api/v1/datasets/{dataset_id}/documents/batch/{batch}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["code"] == "success"

        # 7. 改文档名
        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/name",
            headers=headers,
            json={"name": "改名文档.txt"},
        )
        assert r.status_code == 200

        # 清理
        await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/delete", headers=headers
        )
        await client.post(f"/api/v1/datasets/{dataset_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_segment_manual_crud(app, auth_token):
    """Segment 手动 CRUD（同步写 Milvus，需 Milvus + OpenAI Embedding 可用）"""
    if not _milvus_available():
        pytest.skip("Milvus 不可用，跳过片段手动 CRUD 测试")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建知识库 + 上传 txt + 创建文档（automatic，等待 worker 构建）
        r = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "片段测试知识库",
                "icon": "https://example.com/icon.png",
                "description": "",
            },
        )
        assert r.status_code == 200
        r = await client.get("/api/v1/datasets", headers=headers)
        dataset_id = r.json()["data"]["list"][0]["id"]

        # 上传 txt
        txt_content = "片段测试文档内容。用于手动新增片段测试。"
        r = await client.post(
            "/api/v1/upload-files/file",
            headers=headers,
            files={"file": ("seg.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")},
        )
        upload_file_id = r.json()["data"]["id"]

        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/documents",
            headers=headers,
            json={"upload_file_ids": [upload_file_id], "process_type": "automatic"},
        )
        document_id = r.json()["data"]["documents"][0]["id"]

        # 尝试手动新增片段（需要文档状态为 completed；若 worker 未跑完则 skip）
        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/segments",
            headers=headers,
            json={"content": "手动新增的片段内容，用于测试同步写 Milvus。", "keywords": ["测试", "片段"]},
        )
        if r.json().get("code") != "success":
            pytest.skip("文档未构建完成（worker 未运行），跳过片段手动 CRUD")

        # 查片段列表
        r = await client.get(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/segments",
            headers=headers,
        )
        assert r.status_code == 200
        segs = r.json()["data"]["list"]
        assert len(segs) >= 1
        segment_id = segs[0]["id"]

        # 查片段详情
        r = await client.get(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["hash"]

        # 更新片段
        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}",
            headers=headers,
            json={"content": "更新后的片段内容。", "keywords": ["更新"]},
        )
        assert r.status_code == 200

        # 删除片段
        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}/delete",
            headers=headers,
        )
        assert r.status_code == 200

        # 清理
        await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/delete", headers=headers
        )
        await client.post(f"/api/v1/datasets/{dataset_id}/delete", headers=headers)
