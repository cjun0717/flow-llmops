#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 11.7：微信公众号配置与回调冒烟测试。

签名/XML/状态计算不依赖外部服务；HTTP 联调在 DB 不可用时 skip。
Agent 后台任务在用例中 mock，避免真实 LLM。
"""
from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.entities.app_entity import AppStatus
from app.entities.conversation_entity import InvokeFrom, MessageStatus
from app.entities.platform_entity import WechatConfigStatus
from app.lib.wechat import check_wechat_signature, parse_wechat_message, render_text_reply
from app.main import create_app
from app.schemas.platform import UpdateWechatConfigReq
from app.services.platform_service import PlatformService
from app.services.wechat_service import WechatService


def _sign(token: str, timestamp: str, nonce: str) -> str:
    return hashlib.sha1("".join(sorted([token, timestamp, nonce])).encode()).hexdigest()


def test_update_wechat_config_req_defaults():
    req = UpdateWechatConfigReq()
    assert req.wechat_app_id == ""
    assert req.wechat_app_secret == ""
    assert req.wechat_token == ""


def test_update_wechat_config_req_partial():
    req = UpdateWechatConfigReq(wechat_app_id="wx123")
    assert req.wechat_app_id == "wx123"
    assert req.wechat_token == ""


def test_compute_status_draft_always_unconfigured():
    status = PlatformService.compute_wechat_status(
        AppStatus.DRAFT, "wx", "secret", "token"
    )
    assert status == WechatConfigStatus.UNCONFIGURED


def test_compute_status_published_need_all_fields():
    assert PlatformService.compute_wechat_status(
        AppStatus.PUBLISHED, "wx", "secret", ""
    ) == WechatConfigStatus.UNCONFIGURED
    assert PlatformService.compute_wechat_status(
        AppStatus.PUBLISHED, "wx", "secret", "token"
    ) == WechatConfigStatus.CONFIGURED


def test_check_wechat_signature():
    token, ts, nonce = "hello", "1710000000", "abc"
    signature = _sign(token, ts, nonce)
    assert check_wechat_signature(token, signature, ts, nonce) is True
    assert check_wechat_signature(token, "deadbeef", ts, nonce) is False


def test_parse_and_render_wechat_xml():
    xml = """<xml>
<ToUserName><![CDATA[gh_official]]></ToUserName>
<FromUserName><![CDATA[openid_user]]></FromUserName>
<CreateTime>1348831860</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[你好]]></Content>
<MsgId>1234567890123456</MsgId>
</xml>"""
    msg = parse_wechat_message(xml)
    assert msg is not None
    assert msg.msg_type == "text"
    assert msg.content == "你好"
    assert msg.source == "openid_user"
    assert msg.target == "gh_official"

    reply = render_text_reply(msg, "思考中")
    assert "<ToUserName><![CDATA[openid_user]]></ToUserName>" in reply
    assert "<FromUserName><![CDATA[gh_official]]></FromUserName>" in reply
    assert "<Content><![CDATA[思考中]]></Content>" in reply


def test_parse_empty_xml():
    assert parse_wechat_message(b"") is None
    assert parse_wechat_message("not-xml") is None


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
        pytest.skip(f"数据库不可用，跳过阶段11.7联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段11.7联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段11.7联调: {e}")
        raise

    async with AsyncSessionLocal() as db:
        account = await AccountService.ensure_account(
            email="phase11-wechat@test.local",
            password="Test1234",
            name="阶段11.7测试账号",
            db=db,
        )
        password_hashed, password_salt = AccountService._encode_password("Test1234")
        account.password = password_hashed
        account.password_salt = password_salt
        account.name = "阶段11.7测试账号"
        await db.commit()

    return create_access_token(account.id)


async def _create_app(client: AsyncClient, headers: dict, name: str = "微信测试") -> str:
    r = await client.post(
        "/api/v1/apps",
        headers=headers,
        json={"name": name, "icon": "https://example.com/i.png", "description": "wechat"},
    )
    assert r.json()["code"] == "success", r.text
    return r.json()["data"]["id"]


async def _publish(client: AsyncClient, headers: dict, app_id: str) -> None:
    r = await client.post(f"/api/v1/apps/{app_id}/publish", headers=headers)
    assert r.json()["code"] == "success", r.text


@pytest.mark.asyncio
async def test_platform_unauthorized(app, auth_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(f"/api/v1/platform/{uuid4()}/wechat-config")
        assert r.json()["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_get_and_update_wechat_config(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_id = await _create_app(client, headers)

        r = await client.get(f"/api/v1/platform/{app_id}/wechat-config", headers=headers)
        assert r.json()["code"] == "success", r.text
        data = r.json()["data"]
        assert data["app_id"] == app_id
        assert data["status"] == "unconfigured"
        assert data["wechat_app_id"] == ""
        assert f"/wechat/{app_id}" in data["url"]
        assert "ip" in data

        r = await client.post(
            f"/api/v1/platform/{app_id}/wechat-config",
            headers=headers,
            json={
                "wechat_app_id": "wx123",
                "wechat_app_secret": "secret",
                "wechat_token": "hello-token",
            },
        )
        assert r.json()["code"] == "success"
        assert "更新Agent应用微信公众号配置成功" in r.json()["message"]

        r = await client.get(f"/api/v1/platform/{app_id}/wechat-config", headers=headers)
        data = r.json()["data"]
        assert data["wechat_app_id"] == "wx123"
        assert data["wechat_token"] == "hello-token"
        assert data["status"] == "unconfigured"

        await _publish(client, headers, app_id)
        r = await client.get(f"/api/v1/platform/{app_id}/wechat-config", headers=headers)
        assert r.json()["data"]["status"] == "configured"

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_wechat_get_signature(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_id = await _create_app(client, headers, name="微信签名")
        await _publish(client, headers, app_id)
        await client.post(
            f"/api/v1/platform/{app_id}/wechat-config",
            headers=headers,
            json={
                "wechat_app_id": "wx123",
                "wechat_app_secret": "secret",
                "wechat_token": "hello-token",
            },
        )

        ts, nonce, echostr = "1710000000", "nonce1", "echo-me"
        signature = _sign("hello-token", ts, nonce)
        r = await client.get(
            f"/api/v1/wechat/{app_id}",
            params={"signature": signature, "timestamp": ts, "nonce": nonce, "echostr": echostr},
        )
        assert r.status_code == 200
        assert r.text == echostr

        r = await client.get(
            f"/api/v1/wechat/{app_id}",
            params={"signature": "bad", "timestamp": ts, "nonce": nonce, "echostr": echostr},
        )
        assert r.json()["code"] == "fail"
        assert "接入失败" in r.json()["message"]

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_wechat_get_unpublished(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_id = await _create_app(client, headers, name="未发布微信")
        r = await client.get(
            f"/api/v1/wechat/{app_id}",
            params={"signature": "x", "timestamp": "1", "nonce": "2", "echostr": "3"},
        )
        assert r.json()["code"] == "fail"
        assert "未发布或不存在" in r.json()["message"]
        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_wechat_post_text_and_poll(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    xml = """<xml>
<ToUserName><![CDATA[gh_official]]></ToUserName>
<FromUserName><![CDATA[openid_user]]></FromUserName>
<CreateTime>1348831860</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[你好]]></Content>
</xml>"""

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_id = await _create_app(client, headers, name="微信对话")
        await _publish(client, headers, app_id)
        await client.post(
            f"/api/v1/platform/{app_id}/wechat-config",
            headers=headers,
            json={
                "wechat_app_id": "wx123",
                "wechat_app_secret": "secret",
                "wechat_token": "hello-token",
            },
        )

        with patch.object(WechatService, "background_chat", new_callable=AsyncMock) as bg:
            r = await client.post(
                f"/api/v1/wechat/{app_id}",
                content=xml,
                headers={"Content-Type": "application/xml"},
            )
            assert r.status_code == 200
            assert "思考中" in r.text
            assert "text" in r.headers.get("content-type", "")
            bg.assert_called()

        poll_xml = xml.replace("你好", "1")
        r = await client.post(
            f"/api/v1/wechat/{app_id}",
            content=poll_xml,
            headers={"Content-Type": "application/xml"},
        )
        assert "正在处理中" in r.text or "思考中" in r.text

        r = await client.post(
            f"/api/v1/wechat/{app_id}",
            content=xml.replace("text", "image").replace("你好", ""),
            headers={"Content-Type": "application/xml"},
        )
        assert "只支持文本消息" in r.text

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_wechat_push_completed_answer(app, auth_token):
    from app.db import AsyncSessionLocal
    from app.models.conversation import Conversation, Message
    from app.models.end_user import EndUser
    from app.models.platform import WechatEndUser, WechatMessage

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    xml = """<xml>
<ToUserName><![CDATA[gh_official]]></ToUserName>
<FromUserName><![CDATA[openid_push]]></FromUserName>
<CreateTime>1348831860</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[1]]></Content>
</xml>"""

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_id = await _create_app(client, headers, name="微信推送")
        await _publish(client, headers, app_id)
        await client.post(
            f"/api/v1/platform/{app_id}/wechat-config",
            headers=headers,
            json={
                "wechat_app_id": "wx123",
                "wechat_app_secret": "secret",
                "wechat_token": "hello-token",
            },
        )

        async with AsyncSessionLocal() as db:
            end_user = EndUser(tenant_id=uuid4(), app_id=UUID(app_id))
            db.add(end_user)
            await db.flush()
            we = WechatEndUser(
                openid="openid_push",
                app_id=UUID(app_id),
                end_user_id=end_user.id,
            )
            db.add(we)
            await db.flush()
            conv = Conversation(
                app_id=UUID(app_id),
                name="New Conversation",
                invoke_from=InvokeFrom.SERVICE_API,
                created_by=end_user.id,
            )
            db.add(conv)
            await db.flush()
            msg = Message(
                app_id=UUID(app_id),
                conversation_id=conv.id,
                invoke_from=InvokeFrom.SERVICE_API,
                created_by=end_user.id,
                query="你好",
                answer="这是Agent的回答",
                status=MessageStatus.NORMAL,
            )
            db.add(msg)
            await db.flush()
            db.add(WechatMessage(
                wechat_end_user_id=we.id,
                message_id=msg.id,
                is_pushed=False,
            ))
            await db.commit()

        r = await client.post(
            f"/api/v1/wechat/{app_id}",
            content=xml,
            headers={"Content-Type": "application/xml"},
        )
        assert r.status_code == 200
        assert "这是Agent的回答" in r.text

        with patch.object(WechatService, "background_chat", new_callable=AsyncMock):
            r = await client.post(
                f"/api/v1/wechat/{app_id}",
                content=xml,
                headers={"Content-Type": "application/xml"},
            )
            assert "思考中" in r.text

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)
