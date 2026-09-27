#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""语音服务（async，迁移自 imooc audio_service.py）。

- audio_to_text：Whisper 语音转文本
- message_to_audio：按 message_id 鉴权后 TTS 流式输出
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import AsyncGenerator, Iterator
from io import BytesIO
from uuid import UUID

from openai import OpenAI
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.entities.app_entity import AppStatus
from app.entities.audio_entity import ALLOWED_AUDIO_VOICES
from app.entities.conversation_entity import InvokeFrom
from app.exceptions import FailException, NotFoundException, ValidateException
from app.models.account import Account
from app.models.app import App, AppConfig
from app.models.conversation import Conversation, Message
from app.schemas.response import HttpCode
from app.services.app_service import AppService

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_EXTENSIONS = {"webm", "wav"}
MAX_AUDIO_SIZE = 25 * 1024 * 1024


class AudioService:
    """语音转文本、消息流式输出语音"""

    @staticmethod
    def validate_audio_upload(filename: str | None, size: int) -> str:
        """校验音频文件：必填、≤25MB、仅 webm/wav。返回 Whisper 所需文件名。"""
        if size <= 0:
            raise ValidateException("转换音频文件不能为空")
        if size > MAX_AUDIO_SIZE:
            raise ValidateException("音频文件不能超过25MB")
        name = filename or "recording.wav"
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if extension not in ALLOWED_AUDIO_EXTENSIONS:
            raise ValidateException("请上传正确的音频文件")
        return name

    @classmethod
    def _get_openai_client(cls) -> OpenAI:
        """获取 OpenAI 客户端（Whisper / TTS）"""
        kwargs: dict = {}
        if settings.OPENAI_API_KEY:
            kwargs["api_key"] = settings.OPENAI_API_KEY
        if settings.OPENAI_API_BASE:
            kwargs["base_url"] = settings.OPENAI_API_BASE
        return OpenAI(**kwargs)

    @classmethod
    def _transcribe(cls, content: bytes, filename: str) -> str:
        audio_file = BytesIO(content)
        audio_file.name = filename
        client = cls._get_openai_client()
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return transcription.text

    @classmethod
    async def audio_to_text(cls, audio: UploadFile) -> str:
        """将传递的语音转换成文本"""
        content = await audio.read()
        filename = cls.validate_audio_upload(audio.filename, len(content))
        try:
            return await asyncio.to_thread(cls._transcribe, content, filename)
        except (ValidateException, FailException, NotFoundException):
            raise
        except Exception as error:
            logger.error("语音转文本失败: %s", error, exc_info=True)
            raise FailException("语音转文本失败，请稍后重试") from error

    @staticmethod
    def resolve_tts_config(invoke_from: str, text_to_speech: dict | None) -> tuple[bool, str]:
        """按调用来源解析是否开启 TTS 及音色。开放 API 直接拒绝。"""
        enable = True
        voice = "echo"
        if invoke_from in (InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER, InvokeFrom.WEB_APP.value, InvokeFrom.DEBUGGER.value):
            config = text_to_speech or {}
            enable = bool(config.get("enable", False))
            voice = str(config.get("voice") or "echo")
        elif invoke_from in (InvokeFrom.SERVICE_API, InvokeFrom.SERVICE_API.value):
            raise NotFoundException("开放API消息不支持文本转语音服务")
        if voice not in ALLOWED_AUDIO_VOICES:
            voice = "echo"
        return enable, voice

    @classmethod
    async def prepare_message_to_audio(
        cls, message_id: UUID, account: Account, db: AsyncSession
    ) -> dict:
        """校验消息权限与应用 TTS 配置，返回流式输出所需上下文。"""
        result = await db.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if (
            not message
            or message.is_deleted
            or message.answer.strip() == ""
            or message.created_by != account.id
        ):
            raise NotFoundException("该消息不存在，请核实后重试")

        result = await db.execute(
            select(Conversation).where(Conversation.id == message.conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None or conversation.is_deleted or conversation.created_by != account.id:
            raise NotFoundException("该消息会话不存在，请核实后重试")

        text_to_speech: dict | None = None
        invoke_from = message.invoke_from

        if invoke_from in (InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER, InvokeFrom.WEB_APP.value, InvokeFrom.DEBUGGER.value):
            result = await db.execute(select(App).where(App.id == conversation.app_id))
            app = result.scalar_one_or_none()
            if not app:
                raise NotFoundException("该消息会话归属应用不存在或校验失败，请核实后重试")
            if invoke_from in (InvokeFrom.DEBUGGER, InvokeFrom.DEBUGGER.value) and app.account_id != account.id:
                raise NotFoundException("该消息会话归属的应用不存在或校验失败，请核实后重试")
            if invoke_from in (InvokeFrom.WEB_APP, InvokeFrom.WEB_APP.value) and app.status != AppStatus.PUBLISHED:
                raise NotFoundException("该消息会话归属的应用未发布，请核实后重试")

            if invoke_from in (InvokeFrom.DEBUGGER, InvokeFrom.DEBUGGER.value):
                app_config = await AppService._get_draft_config(app.id, db)
            else:
                result = await db.execute(select(AppConfig).where(AppConfig.id == app.app_config_id))
                app_config = result.scalar_one_or_none()
            text_to_speech = getattr(app_config, "text_to_speech", None) if app_config else None

        enable, voice = cls.resolve_tts_config(invoke_from, text_to_speech)
        if enable is False:
            raise FailException("该应用未开启文字转语音功能，请核实后重试")

        return {
            "conversation_id": conversation.id,
            "message_id": message.id,
            "answer": message.answer.strip(),
            "voice": voice,
        }

    @classmethod
    def _iter_speech_chunks(cls, text: str, voice: str) -> Iterator[bytes]:
        """调用 OpenAI TTS，按 1024 字节分块（便于单测 mock）。"""
        client = cls._get_openai_client()
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=voice,
            response_format="mp3",
            input=text,
        ) as response:
            yield from response.iter_bytes(1024)

    @classmethod
    async def stream_tts(
        cls,
        *,
        conversation_id: UUID,
        message_id: UUID,
        answer: str,
        voice: str,
    ) -> AsyncGenerator[str, None]:
        """将文本转换成 SSE 语音事件。"""
        common_data = {
            "conversation_id": str(conversation_id),
            "message_id": str(message_id),
            "audio": "",
        }
        try:
            loop = asyncio.get_running_loop()
            sync_gen = cls._iter_speech_chunks(answer, voice)
            sentinel = object()

            def _next_or_none(it):
                try:
                    return next(it)
                except StopIteration:
                    return sentinel

            while True:
                chunk = await loop.run_in_executor(None, _next_or_none, sync_gen)
                if chunk is sentinel:
                    break
                data = {**common_data, "audio": base64.b64encode(chunk).decode("utf-8")}
                yield f"event: tts_message\ndata: {json.dumps(data)}\n\n"
            yield f"event: tts_end\ndata: {json.dumps(common_data)}\n\n"
        except Exception as error:
            logger.error("文字转语音失败: %s", error, exc_info=True)
            yield "event: error\ndata:" + json.dumps({
                "code": HttpCode.FAIL.value,
                "message": "文字转语音失败，请稍后重试",
                "data": {},
            }, ensure_ascii=False) + "\n\n"
