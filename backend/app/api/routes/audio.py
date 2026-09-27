#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""语音路由（迁移自 imooc audio_handler.py）。"""
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep
from app.schemas.audio import AudioToTextData, MessageToAudioReq
from app.schemas.response import ApiResponse, ok
from app.services.audio_service import AudioService

router = APIRouter(prefix="/audio", tags=["语音"])


@router.post("/audio-to-text", response_model=ApiResponse[AudioToTextData])
async def audio_to_text(
    _account: CurrentAccount,
    file: UploadFile = File(..., description="语音音频源文件"),
) -> ApiResponse[AudioToTextData]:
    """将语音转换成文本"""
    text = await AudioService.audio_to_text(file)
    return ok(AudioToTextData(text=text))


@router.post("/message-to-audio")
async def message_to_audio(
    body: MessageToAudioReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> StreamingResponse:
    """将消息转换成流式输出音频（SSE）"""
    ctx = await AudioService.prepare_message_to_audio(body.message_id, account, db)
    return StreamingResponse(
        AudioService.stream_tts(**ctx),
        status_code=200,
        media_type="text/event-stream",
    )
