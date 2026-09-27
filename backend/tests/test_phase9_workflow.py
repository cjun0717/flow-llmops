#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 9：工作流 CRUD + 草稿图 + 发布 冒烟测试。

注意：debug_workflow SSE 流式依赖真实 LLM/工具调用，无凭证时跳过；
其余 CRUD/草稿图/发布用例仅需数据库。Docker 服务停止时整体跳过。
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db import AsyncSessionLocal, init_create_table
from app.entities.workflow_entity import WorkflowStatus
from app.main import create_app
from app.models.account import Account
from app.models.workflow import Workflow
from app.services.account_service import AccountService
from app.utils.jwt import create_access_token

TEST_EMAIL = "phase9@test.local"
TEST_PASSWORD = "Test1234"
TEST_NAME = "阶段9测试账号"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
async def auth_token():
    try:
        await init_create_table()
    except OSError as e:
        pytest.skip(f"数据库不可用，跳过阶段9联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段9联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段9联调: {e}")
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


def _minimal_graph() -> dict:
    """构建一个最小合法工作流图：start -> end，start 有一个输入，end 输出引用 start"""
    start_id = str(uuid4())
    end_id = str(uuid4())
    edge_id = str(uuid4())
    return {
        "nodes": [
            {
                "id": start_id,
                "node_type": "start",
                "title": "开始",
                "description": "开始节点",
                "position": {"x": 0, "y": 0},
                "inputs": [
                    {
                        "name": "query",
                        "description": "用户输入",
                        "required": True,
                        "type": "string",
                        "value": {"type": "literal", "content": ""},
                    }
                ],
            },
            {
                "id": end_id,
                "node_type": "end",
                "title": "结束",
                "description": "结束节点",
                "position": {"x": 200, "y": 0},
                "outputs": [
                    {
                        "name": "result",
                        "description": "输出结果",
                        "required": True,
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": start_id,
                                "ref_var_name": "query",
                            },
                        },
                    }
                ],
            },
        ],
        "edges": [
            {
                "id": edge_id,
                "source": start_id,
                "source_type": "start",
                "source_handle_id": None,
                "target": end_id,
                "target_type": "end",
            }
        ],
    }


@pytest.mark.asyncio
async def test_phase9_workflow_crud(app, auth_token):
    """工作流 CRUD 完整流程：创建→列表→详情→改名→删除"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建工作流
        r = await client.post(
            "/api/v1/workflows",
            headers=headers,
            json={
                "name": "阶段9工作流",
                "tool_call_name": "phase9_workflow",
                "icon": "https://example.com/icon.png",
                "description": "阶段9测试工作流",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        workflow_id = body["data"]["id"]

        # 2. 获取详情
        r = await client.get(f"/api/v1/workflows/{workflow_id}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        assert body["data"]["name"] == "阶段9工作流"
        assert body["data"]["tool_call_name"] == "phase9_workflow"
        assert body["data"]["status"] == WorkflowStatus.DRAFT

        # 3. 列表
        r = await client.get("/api/v1/workflows", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        assert body["data"]["paginator"]["total_record"] >= 1

        # 4. 改名
        r = await client.post(
            f"/api/v1/workflows/{workflow_id}",
            headers=headers,
            json={
                "name": "阶段9工作流改名",
                "tool_call_name": "phase9_workflow",
                "icon": "https://example.com/icon2.png",
                "description": "阶段9测试工作流改描述",
            },
        )
        assert r.status_code == 200, r.text
        r = await client.get(f"/api/v1/workflows/{workflow_id}", headers=headers)
        assert r.json()["data"]["name"] == "阶段9工作流改名"

        # 5. 删除
        r = await client.post(f"/api/v1/workflows/{workflow_id}/delete", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success"


@pytest.mark.asyncio
async def test_phase9_draft_graph_and_publish(app, auth_token):
    """草稿图更新/读取 + 发布/取消发布流程"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建工作流
        r = await client.post(
            "/api/v1/workflows",
            headers=headers,
            json={
                "name": "阶段9草稿图工作流",
                "tool_call_name": "phase9_draft",
                "icon": "https://example.com/icon.png",
                "description": "阶段9草稿图测试",
            },
        )
        assert r.status_code == 200, r.text
        workflow_id = r.json()["data"]["id"]

        # 2. 更新草稿图（最小合法图）
        graph = _minimal_graph()
        r = await client.post(
            f"/api/v1/workflows/{workflow_id}/draft-graph",
            headers=headers,
            json=graph,
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success"

        # 3. 读取草稿图
        r = await client.get(
            f"/api/v1/workflows/{workflow_id}/draft-graph", headers=headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        draft = body["data"]
        # 校验后节点数应保持为 2
        assert len(draft["nodes"]) == 2
        assert len(draft["edges"]) == 1

        # 4. 未调试通过直接发布应失败
        r = await client.post(
            f"/api/v1/workflows/{workflow_id}/publish", headers=headers
        )
        body = r.json()
        assert body["code"] == "fail"

        # 5. 手动标记调试通过后发布
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
            workflow = result.scalar_one()
            workflow.is_debug_passed = True
            await db.commit()

        r = await client.post(
            f"/api/v1/workflows/{workflow_id}/publish", headers=headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success"

        # 6. 校验已发布
        r = await client.get(f"/api/v1/workflows/{workflow_id}", headers=headers)
        assert r.json()["data"]["status"] == WorkflowStatus.PUBLISHED

        # 7. 取消发布
        r = await client.post(
            f"/api/v1/workflows/{workflow_id}/cancel-publish", headers=headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "success"
        r = await client.get(f"/api/v1/workflows/{workflow_id}", headers=headers)
        assert r.json()["data"]["status"] == WorkflowStatus.DRAFT

        # 8. 清理
        await client.post(f"/api/v1/workflows/{workflow_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_phase9_workflow_validate_graph(app, auth_token):
    """草稿图校验：重复 id / 非法节点类型应被宽松校验过滤"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 创建工作流
        r = await client.post(
            "/api/v1/workflows",
            headers=headers,
            json={
                "name": "阶段9校验工作流",
                "tool_call_name": "phase9_validate",
                "icon": "https://example.com/icon.png",
                "description": "阶段9校验测试",
            },
        )
        assert r.status_code == 200, r.text
        workflow_id = r.json()["data"]["id"]

        # 2. 构造含非法节点类型的草稿图（应被宽松校验过滤掉）
        start_id = str(uuid4())
        end_id = str(uuid4())
        bad_id = str(uuid4())
        edge_id = str(uuid4())
        graph = {
            "nodes": [
                {
                    "id": start_id,
                    "node_type": "start",
                    "title": "开始",
                    "inputs": [],
                },
                {
                    "id": end_id,
                    "node_type": "end",
                    "title": "结束",
                    "outputs": [],
                },
                {
                    "id": bad_id,
                    "node_type": "unknown_type",
                    "title": "非法节点",
                },
            ],
            "edges": [
                {
                    "id": edge_id,
                    "source": start_id,
                    "source_type": "start",
                    "source_handle_id": None,
                    "target": end_id,
                    "target_type": "end",
                }
            ],
        }
        r = await client.post(
            f"/api/v1/workflows/{workflow_id}/draft-graph",
            headers=headers,
            json=graph,
        )
        assert r.status_code == 200, r.text

        # 3. 读取草稿图，非法节点应被过滤
        r = await client.get(
            f"/api/v1/workflows/{workflow_id}/draft-graph", headers=headers
        )
        body = r.json()
        assert body["code"] == "success", body
        titles = [node["title"] for node in body["data"]["nodes"]]
        assert "非法节点" not in titles
        assert len(body["data"]["nodes"]) == 2

        # 4. 清理
        await client.post(f"/api/v1/workflows/{workflow_id}/delete", headers=headers)
