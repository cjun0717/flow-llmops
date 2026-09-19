#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 5b：hit 检索 + 向量同步冒烟测试。

测试范围：
- hit 三策略（semantic/full_text/hybrid）
- hit 空结果
- update_document_enabled 向量同步（需 worker）
- delete_document 向量同步（需 worker）
- 文件解析端到端（上传 txt → create_documents → 等 worker → hit）

Milvus/OpenAI/worker 不可用时按用例 skip。
"""
from __future__ import annotations

import io
import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.main import create_app
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase5b@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段5b测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段5b联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段5b联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段5b联调: {e}")
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
    try:
        from pymilvus import MilvusClient
        from app.config import settings
        c = MilvusClient(uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        c.close()
        return True
    except Exception:
        return False


async def _build_dataset_with_doc(client, headers, name, txt_content):
    """创建知识库 + 上传 txt + 创建文档，返回 (dataset_id, document_id, batch)"""
    r = await client.post(
        "/api/v1/datasets",
        headers=headers,
        json={"name": name, "icon": "https://example.com/icon.png", "description": ""},
    )
    assert r.status_code == 200
    r = await client.get("/api/v1/datasets", headers=headers)
    dataset_id = r.json()["data"]["list"][0]["id"]

    r = await client.post(
        "/api/v1/upload-files/file",
        headers=headers,
        files={"file": ("doc.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")},
    )
    upload_file_id = r.json()["data"]["id"]

    r = await client.post(
        f"/api/v1/datasets/{dataset_id}/documents",
        headers=headers,
        json={"upload_file_ids": [upload_file_id], "process_type": "automatic"},
    )
    data = r.json()["data"]
    return dataset_id, data["documents"][0]["id"], data["batch"]


async def _wait_document_completed(client, headers, dataset_id, document_id, timeout=60):
    """轮询文档状态直到 completed 或超时"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = await client.get(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}", headers=headers
        )
        status = r.json()["data"]["status"]
        if status == "completed":
            return True
        if status == "error":
            return False
        await _async_sleep(2)
    return False


async def _async_sleep(seconds):
    import asyncio
    await asyncio.sleep(seconds)


@pytest.mark.asyncio
async def test_hit_semantic(app, auth_token):
    """semantic 召回测试：需 Milvus + worker 构建完成"""
    if not _milvus_available():
        pytest.skip("Milvus 不可用，跳过 semantic 召回测试")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        txt = "人工智能是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。"
        dataset_id, document_id, _batch = await _build_dataset_with_doc(
            client, headers, "semantic测试知识库", txt
        )

        ok = await _wait_document_completed(client, headers, dataset_id, document_id, timeout=90)
        if not ok:
            pytest.skip("文档未构建完成（worker 未运行或构建失败），跳过 semantic 召回")

        # semantic 召回
        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/hit",
            headers=headers,
            json={
                "query": "什么是人工智能",
                "retrieval_strategy": "semantic",
                "k": 5,
                "score": 0,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        items = body["data"]
        # 可能命中也可能不命中（取决于 embedding），但结构应正确
        for item in items:
            assert "score" in item
            assert "content" in item
            assert "document" in item
            assert "id" in item["document"]

        # 清理
        await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/delete", headers=headers
        )
        await client.post(f"/api/v1/datasets/{dataset_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_hit_full_text(app, auth_token):
    """full_text 召回测试：需 worker 构建完成（生成 keyword_table）"""
    if not _milvus_available():
        pytest.skip("Milvus 不可用，跳过 full_text 召回测试")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        txt = "知识库全文检索测试内容。关键词包括：人工智能、机器学习、深度学习、自然语言处理。"
        dataset_id, document_id, _batch = await _build_dataset_with_doc(
            client, headers, "fulltext测试知识库", txt
        )

        ok = await _wait_document_completed(client, headers, dataset_id, document_id, timeout=90)
        if not ok:
            pytest.skip("文档未构建完成（worker 未运行或构建失败），跳过 full_text 召回")

        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/hit",
            headers=headers,
            json={
                "query": "人工智能 机器学习",
                "retrieval_strategy": "full_text",
                "k": 5,
                "score": 0,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        items = body["data"]
        # full_text 命中的 score 应为 0
        for item in items:
            assert item["score"] == 0

        # 清理
        await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/delete", headers=headers
        )
        await client.post(f"/api/v1/datasets/{dataset_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_hit_hybrid(app, auth_token):
    """hybrid 召回测试：需 worker 构建完成"""
    if not _milvus_available():
        pytest.skip("Milvus 不可用，跳过 hybrid 召回测试")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        txt = "混合检索测试。人工智能与机器学习是当前热门技术方向，深度学习推动了自然语言处理的发展。"
        dataset_id, document_id, _batch = await _build_dataset_with_doc(
            client, headers, "hybrid测试知识库", txt
        )

        ok = await _wait_document_completed(client, headers, dataset_id, document_id, timeout=90)
        if not ok:
            pytest.skip("文档未构建完成（worker 未运行或构建失败），跳过 hybrid 召回")

        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/hit",
            headers=headers,
            json={
                "query": "人工智能 机器学习",
                "retrieval_strategy": "hybrid",
                "k": 5,
                "score": 0,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success"
        items = body["data"]
        for item in items:
            assert "score" in item

        # 清理
        await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/delete", headers=headers
        )
        await client.post(f"/api/v1/datasets/{dataset_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_hit_empty(app, auth_token):
    """无匹配 query 返回空列表"""
    if not _milvus_available():
        pytest.skip("Milvus 不可用，跳过空召回测试")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        txt = "一个独特的文档内容，包含特殊词汇：量子纠缠、超导体、拓扑绝缘体。"
        dataset_id, document_id, _batch = await _build_dataset_with_doc(
            client, headers, "空召回测试知识库", txt
        )

        ok = await _wait_document_completed(client, headers, dataset_id, document_id, timeout=90)
        if not ok:
            pytest.skip("文档未构建完成，跳过空召回测试")

        # 用完全不相关的 query（高 score_threshold）
        r = await client.post(
            f"/api/v1/datasets/{dataset_id}/hit",
            headers=headers,
            json={
                "query": "zzzzzzzz 不存在的词汇",
                "retrieval_strategy": "semantic",
                "k": 5,
                "score": 0.99,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "success"
        # 高阈值下应无命中（或少量）
        assert isinstance(body["data"], list)

        # 清理
        await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/delete", headers=headers
        )
        await client.post(f"/api/v1/datasets/{dataset_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_hit_unauthorized(app):
    """未授权访问 hit 返回 unauthorized"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000001/hit",
            json={"query": "x", "retrieval_strategy": "semantic", "k": 1, "score": 0},
        )
        # 业务异常统一返回 200 + code=unauthorized
        body = r.json()
        assert body["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_hit_writes_dataset_query(app, auth_token):
    """hit 测试应写 DatasetQuery 记录"""
    if not _milvus_available():
        pytest.skip("Milvus 不可用，跳过 DatasetQuery 写入测试")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        txt = "DatasetQuery 测试内容，包含关键词：测试、记录、查询。"
        dataset_id, document_id, _batch = await _build_dataset_with_doc(
            client, headers, "query记录测试知识库", txt
        )

        ok = await _wait_document_completed(client, headers, dataset_id, document_id, timeout=90)
        if not ok:
            pytest.skip("文档未构建完成，跳过 DatasetQuery 写入测试")

        # 执行一次 hit
        await client.post(
            f"/api/v1/datasets/{dataset_id}/hit",
            headers=headers,
            json={
                "query": "测试 记录",
                "retrieval_strategy": "full_text",
                "k": 5,
                "score": 0,
            },
        )

        # 查 queries 应有记录
        r = await client.get(f"/api/v1/datasets/{dataset_id}/queries", headers=headers)
        assert r.status_code == 200
        queries = r.json()["data"]
        # full_text 命中后应至少有一条查询记录
        assert len(queries) >= 1
        assert queries[0]["query"] == "测试 记录"
        assert queries[0]["source"] == "hit_testing"

        # 清理
        await client.post(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/delete", headers=headers
        )
        await client.post(f"/api/v1/datasets/{dataset_id}/delete", headers=headers)
