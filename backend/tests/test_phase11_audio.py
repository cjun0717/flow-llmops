#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 11.6：语音（STT / TTS）冒烟测试。

文件校验与 TTS 配置解析不依赖外部服务；HTTP 联调在 DB 不可用时 skip。
真实 Whisper/TTS 无 OPENAI_API_KEY 时跳过。
"""
from __future__ import annotations

import base64
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.entities.conversation_entity import InvokeFrom, MessageStatus
from app.exceptions import NotFoundException, ValidateException
from app.main import create_app
from app.schemas.audio import MessageToAudioReq
from app.services.audio_service import MAX_AUDIO_SIZE, AudioService


def test_message_to_audio_req_valid():
    msg_id = uuid4()
    req = MessageToAudioReq(message_id=msg_id)
    assert req.message_id == msg_id


def test_message_to_audio_req_invalid_uuid():
    with pytest.raises(ValidationError):
        MessageToAudioReq(message_id="not-a-uuid")


def test_validate_audio_upload_ok():
    assert AudioService.validate_audio_upload("recording.wav", 12) == "recording.wav"
    assert AudioService.validate_audio_upload("voice.WEBM", 8) == "voice.WEBM"


def test_validate_audio_upload_empty():
    with pytest.raises(ValidateException, match="不能为空"):
        AudioService.validate_audio_upload("recording.wav", 0)


def test_validate_audio_upload_too_large():
    with pytest.raises(ValidateException, match="25MB"):
        AudioService.validate_audio_upload("recording.wav", MAX_AUDIO_SIZE + 1)


def test_validate_audio_upload_wrong_type():
    with pytest.raises(ValidateException, match="正确的音频文件"):
        AudioService.validate_audio_upload("note.mp3", 10)


def test_resolve_tts_debugger_and_web_app():
    enable, voice = AudioService.resolve_tts_config(
        InvokeFrom.DEBUGGER, {"enable": True, "voice": "nova", "auto_play": True}
    )
    assert enable is True
    assert voice == "nova"

    enable, voice = AudioService.resolve_tts_config(InvokeFrom.WEB_APP, {"enable": False, "voice": "echo"})
    assert enable is False
    assert voice == "echo"


def test_resolve_tts_service_api_rejected():
    with pytest.raises(NotFoundException, match="开放API"):
        AudioService.resolve_tts_config(InvokeFrom.SERVICE_API, None)


def test_resolve_tts_assistant_agent_defaults():
    enable, voice = AudioService.resolve_tts_config(InvokeFrom.ASSISTANT_AGENT, None)
    assert enable is True
    assert voice == "echo"


def test_resolve_tts_invalid_voice_fallback():
    enable, voice = AudioService.resolve_tts_config(
        InvokeFrom.DEBUGGER, {"enable": True, "voice": "not-a-voice"}
    )
    assert enable is True
    assert voice == "echo"


@pytest.mark.asyncio
async def test_stream_tts_sse_format():
    conversation_id = uuid4()
    message_id = uuid4()

    with patch.object(AudioService, "_iter_speech_chunks", return_value=iter([b"abc", b"def"])):
        events = []
        async for chunk in AudioService.stream_tts(
            conversation_id=conversation_id,
            message_id=message_id,
            answer="你好",
            voice="echo",
        ):
            events.append(chunk)

    assert len(events) == 3
    assert events[0].startswith("event: tts_message\n")
    assert events[1].startswith("event: tts_message\n")
    assert events[2].startswith("event: tts_end\n")

    first = json.loads(events[0].split("data: ", 1)[1].strip())
    assert first["conversation_id"] == str(conversation_id)
    assert first["message_id"] == str(message_id)
    assert first["audio"] == base64.b64encode(b"abc").decode("utf-8")

    end = json.loads(events[2].split("data: ", 1)[1].strip())
    assert end["audio"] == ""


@pytest.mark.asyncio
async def test_stream_tts_error_event():
    with patch.object(AudioService, "_iter_speech_chunks", side_effect=RuntimeError("boom")):
        events = []
        async for chunk in AudioService.stream_tts(
            conversation_id=uuid4(),
            message_id=uuid4(),
            answer="你好",
            voice="echo",
        ):
            events.append(chunk)

    assert len(events) == 1
    assert events[0].startswith("event: error\n")
    payload = json.loads(events[0].split("data:", 1)[1].strip())
    assert payload["code"] == "fail"
    assert "文字转语音失败" in payload["message"]


@pytest.mark.asyncio
async def test_audio_to_text_calls_whisper():
    upload = MagicMock()
    upload.filename = "recording.wav"
    upload.read = AsyncMock(return_value=b"fake-wav")

    with patch.object(AudioService, "_transcribe", return_value="慕课网，程序员的梦工厂") as transcribe:
        text = await AudioService.audio_to_text(upload)

    assert text == "慕课网，程序员的梦工厂"
    transcribe.assert_called_once_with(b"fake-wav", "recording.wav")


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
        pytest.skip(f"数据库不可用，跳过阶段11.6联调: {e}")
    except OperationalError as e:
        pytest.skip(f"数据库不可用，跳过阶段11.6联调: {e}")
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"数据库不可用，跳过阶段11.6联调: {e}")
        raise

    async with AsyncSessionLocal() as db:
        account = await AccountService.ensure_account(
            email="phase11-audio@test.local",
            password="Test1234",
            name="阶段11.6测试账号",
            db=db,
        )
        password_hashed, password_salt = AccountService._encode_password("Test1234")
        account.password = password_hashed
        account.password_salt = password_salt
        account.name = "阶段11.6测试账号"
        await db.commit()

    return create_access_token(account.id)


@pytest.mark.asyncio
async def test_audio_unauthorized(app, auth_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/audio/audio-to-text")
        assert r.json()["code"] == "unauthorized"

        r = await client.post(
            "/api/v1/audio/message-to-audio",
            json={"message_id": str(uuid4())},
        )
        assert r.json()["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_audio_to_text_http_mocked(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch.object(AudioService, "_transcribe", return_value="你好世界"):
            r = await client.post(
                "/api/v1/audio/audio-to-text",
                headers=headers,
                files={"file": ("recording.wav", b"fake-audio", "audio/wav")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "success"
        assert body["data"]["text"] == "你好世界"

        r = await client.post(
            "/api/v1/audio/audio-to-text",
            headers=headers,
            files={"file": ("note.mp3", b"xxx", "audio/mpeg")},
        )
        assert r.json()["code"] == "validate_error"


@pytest.mark.asyncio
async def test_message_to_audio_not_found(app, auth_token):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/audio/message-to-audio",
            headers=headers,
            json={"message_id": str(uuid4())},
        )
        assert r.json()["code"] == "not_found"


@pytest.mark.asyncio
async def test_message_to_audio_tts_disabled(app, auth_token):
    from app.db import AsyncSessionLocal
    from app.models.account import Account
    from app.models.conversation import Conversation, Message
    from sqlalchemy import select

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={"name": "语音测试关闭", "icon": "https://example.com/i.png", "description": "tts"},
        )
        assert r.json()["code"] == "success", r.text
        app_id = r.json()["data"]["id"]

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Account).where(Account.email == "phase11-audio@test.local"))
            account = result.scalar_one()
            conv = Conversation(
                app_id=UUID(app_id),
                name="调试会话",
                invoke_from=InvokeFrom.DEBUGGER,
                created_by=account.id,
            )
            db.add(conv)
            await db.flush()
            msg = Message(
                app_id=UUID(app_id),
                conversation_id=conv.id,
                invoke_from=InvokeFrom.DEBUGGER,
                created_by=account.id,
                query="你好",
                answer="你好，有什么可以帮你？",
                status=MessageStatus.NORMAL,
            )
            db.add(msg)
            await db.flush()
            message_id = msg.id
            await db.commit()

        r = await client.post(
            "/api/v1/audio/message-to-audio",
            headers=headers,
            json={"message_id": str(message_id)},
        )
        body = r.json()
        assert body["code"] == "fail"
        assert "未开启文字转语音" in body["message"]

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_message_to_audio_sse_mocked(app, auth_token):
    from app.db import AsyncSessionLocal
    from app.models.account import Account
    from app.models.conversation import Conversation, Message
    from sqlalchemy import select

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/apps",
            headers=headers,
            json={"name": "语音测试开启", "icon": "https://example.com/i.png", "description": "tts"},
        )
        assert r.json()["code"] == "success", r.text
        app_id = r.json()["data"]["id"]

        r = await client.post(
            f"/api/v1/apps/{app_id}/draft-app-config",
            headers=headers,
            json={"text_to_speech": {"enable": True, "voice": "echo", "auto_play": False}},
        )
        assert r.json()["code"] == "success", r.text

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Account).where(Account.email == "phase11-audio@test.local"))
            account = result.scalar_one()
            conv = Conversation(
                app_id=UUID(app_id),
                name="调试会话",
                invoke_from=InvokeFrom.DEBUGGER,
                created_by=account.id,
            )
            db.add(conv)
            await db.flush()
            msg = Message(
                app_id=UUID(app_id),
                conversation_id=conv.id,
                invoke_from=InvokeFrom.DEBUGGER,
                created_by=account.id,
                query="你好",
                answer="你好，这是一段测试回复。",
                status=MessageStatus.NORMAL,
            )
            db.add(msg)
            await db.flush()
            message_id = msg.id
            await db.commit()

        with patch.object(AudioService, "_iter_speech_chunks", return_value=iter([b"mp3-bytes"])):
            async with client.stream(
                "POST",
                "/api/v1/audio/message-to-audio",
                headers=headers,
                json={"message_id": str(message_id)},
            ) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                text = ""
                async for line in resp.aiter_lines():
                    text += line + "\n"
                assert "event: tts_message" in text
                assert "event: tts_end" in text
                assert base64.b64encode(b"mp3-bytes").decode("utf-8") in text

        await client.post(f"/api/v1/apps/{app_id}/delete", headers=headers)


@pytest.mark.asyncio
async def test_message_to_audio_service_api_rejected(app, auth_token):
    from app.db import AsyncSessionLocal
    from app.models.account import Account
    from app.models.conversation import Conversation, Message
    from sqlalchemy import select

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Account).where(Account.email == "phase11-audio@test.local"))
            account = result.scalar_one()
            app_id = uuid4()
            conv = Conversation(
                app_id=app_id,
                name="开放API会话",
                invoke_from=InvokeFrom.SERVICE_API,
                created_by=account.id,
            )
            db.add(conv)
            await db.flush()
            msg = Message(
                app_id=app_id,
                conversation_id=conv.id,
                invoke_from=InvokeFrom.SERVICE_API,
                created_by=account.id,
                query="hello",
                answer="world",
                status=MessageStatus.NORMAL,
            )
            db.add(msg)
            await db.flush()
            message_id = msg.id
            await db.commit()

        r = await client.post(
            "/api/v1/audio/message-to-audio",
            headers=headers,
            json={"message_id": str(message_id)},
        )
        assert r.json()["code"] == "not_found"
        assert "开放API" in r.json()["message"]


@pytest.mark.asyncio
async def test_audio_to_text_real_whisper(app, auth_token):
    if not (os.getenv("OPENAI_API_KEY") or ""):
        pytest.skip("未设置 OPENAI_API_KEY，跳过 Whisper 联调")

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        r = await client.post(
            "/api/v1/audio/audio-to-text",
            headers=headers,
            files={"file": ("recording.wav", b"not-real-audio", "audio/wav")},
        )
        assert r.status_code == 200
        assert r.json()["code"] in ("success", "fail")
