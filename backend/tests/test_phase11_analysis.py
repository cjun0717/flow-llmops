#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 11.4：应用统计分析冒烟测试。

指标计算不依赖外部服务；HTTP 联调在 DB 不可用时 skip。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.main import create_app
from app.services.analysis_service import AnalysisService


def _msg(
    *,
    created_by=None,
    conversation_id=None,
    latency=1.0,
    total_token_count=10,
    total_price=1.5,
    created_at=None,
):
    return SimpleNamespace(
        created_by=created_by or uuid4(),
        conversation_id=conversation_id or uuid4(),
        latency=latency,
        total_token_count=total_token_count,
        total_price=total_price,
        created_at=created_at or datetime.now(),
    )


def test_overview_indicators_empty():
    result = AnalysisService.calculate_overview_indicators_by_messages([])
    assert result["total_messages"] == 0
    assert result["active_accounts"] == 0
    assert result["avg_of_conversation_messages"] == 0
    assert result["token_output_rate"] == 0
    assert result["cost_consumption"] == 0


def test_overview_indicators_with_messages():
    user_a, user_b = uuid4(), uuid4()
    conv = uuid4()
    messages = [
        _msg(created_by=user_a, conversation_id=conv, latency=2, total_token_count=20, total_price=3),
        _msg(created_by=user_b, conversation_id=conv, latency=2, total_token_count=20, total_price=1),
    ]
    result = AnalysisService.calculate_overview_indicators_by_messages(messages)
    assert result["total_messages"] == 2
    assert result["active_accounts"] == 2
    assert result["avg_of_conversation_messages"] == 2.0
    assert result["token_output_rate"] == 10.0  # 40 tokens / 4s
    assert result["cost_consumption"] == 4.0


def test_pop_when_previous_zero():
    current = {"total_messages": 10, "active_accounts": 1, "avg_of_conversation_messages": 2,
               "token_output_rate": 1, "cost_consumption": 3}
    previous = {k: 0 for k in current}
    pop = AnalysisService.calculate_pop_by_overview_indicators(current, previous)
    assert pop["total_messages"] == 0
    assert pop["cost_consumption"] == 0


def test_pop_growth_rate():
    current = {"total_messages": 15, "active_accounts": 6, "avg_of_conversation_messages": 3,
               "token_output_rate": 2, "cost_consumption": 12}
    previous = {"total_messages": 10, "active_accounts": 3, "avg_of_conversation_messages": 3,
                "token_output_rate": 1, "cost_consumption": 4}
    pop = AnalysisService.calculate_pop_by_overview_indicators(current, previous)
    assert pop["total_messages"] == 0.5
    assert pop["active_accounts"] == 1.0
    assert pop["avg_of_conversation_messages"] == 0.0
    assert pop["token_output_rate"] == 1.0
    assert pop["cost_consumption"] == 2.0


def test_trend_has_seven_days():
    end_at = datetime.combine(datetime.now(), datetime.min.time())
    day1 = end_at - timedelta(days=7)
    day2 = end_at - timedelta(days=1)
    conv = uuid4()
    user = uuid4()
    messages = [
        _msg(created_by=user, conversation_id=conv, total_price=2, created_at=day1 + timedelta(hours=3)),
        _msg(created_by=user, conversation_id=conv, total_price=3, created_at=day2 + timedelta(hours=1)),
        _msg(created_by=uuid4(), conversation_id=uuid4(), total_price=1, created_at=day2 + timedelta(hours=2)),
    ]
    trend = AnalysisService.calculate_trend_by_messages(end_at, 7, messages)
    assert len(trend["total_messages_trend"]["x_axis"]) == 7
    assert len(trend["total_messages_trend"]["y_axis"]) == 7
    assert trend["total_messages_trend"]["y_axis"][0] == 1
    assert trend["total_messages_trend"]["y_axis"][-1] == 2
    assert trend["active_accounts_trend"]["y_axis"][-1] == 2
    assert trend["cost_consumption_trend"]["y_axis"][-1] == 4.0
    assert trend["avg_of_conversation_messages_trend"]["y_axis"][-1] == 1.0


@pytest.mark.asyncio
async def test_get_app_analysis_returns_cache():
    """Redis 命中时不再查库"""
    app = MagicMock()
    app.id = uuid4()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value='{"total_messages": {"data": 9, "pop": 0}}')
    db = AsyncMock()

    with patch(
        "app.services.analysis_service.AppService.get_app",
        new=AsyncMock(return_value=app),
    ):
        result = await AnalysisService.get_app_analysis(app.id, MagicMock(), db, redis)

    assert result["total_messages"]["data"] == 9
    db.execute.assert_not_called()


# ===== 需数据库的联调 =====


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
        pytest.skip(f"数据库不可用，跳过阶段11.4联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段11.4联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段11.4联调: {e}")
        raise

    async with AsyncSessionLocal() as db:
        account = await AccountService.ensure_account(
            email="phase11-analysis@test.local",
            password="Test1234",
            name="阶段11.4测试账号",
            db=db,
        )
        password_hashed, password_salt = AccountService._encode_password("Test1234")
        account.password = password_hashed
        account.password_salt = password_salt
        account.name = "阶段11.4测试账号"
        await db.commit()

    return create_access_token(account.id)


@pytest.mark.asyncio
async def test_analysis_unauthorized(app, auth_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(f"/api/v1/analysis/{uuid4()}")
        assert r.json()["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_analysis_not_found(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(f"/api/v1/analysis/{uuid4()}", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == "not_found"


@pytest.mark.asyncio
async def test_analysis_empty_app(app, auth_token):
    """新建应用、无消息时指标全为 0，趋势为 7 天"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={"name": "统计测试应用", "icon": "https://example.com/i.png", "description": "分析"},
        )
        assert r.json()["code"] == "success", r.text
        app_id = r.json()["data"]["id"]

        r = await client.get(f"/api/v1/analysis/{app_id}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "success", body
        data = body["data"]
        assert data["total_messages"]["data"] == 0
        assert data["active_accounts"]["data"] == 0
        assert data["avg_of_conversation_messages"]["pop"] == 0
        assert len(data["total_messages_trend"]["x_axis"]) == 7
        assert data["total_messages_trend"]["y_axis"] == [0, 0, 0, 0, 0, 0, 0]
        assert "avg_of_conversation_messages_trend" in data

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
