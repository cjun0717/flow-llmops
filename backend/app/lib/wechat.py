#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""微信公众号签名校验与 XML 解析/回复（对齐 wechatpy 的最小子集，不引入额外运行时）。"""
from __future__ import annotations

import hashlib
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass
class WechatInboundMessage:
    """入站消息（source=FromUserName/openid，target=ToUserName）"""
    msg_type: str
    content: str
    source: str
    target: str


def check_wechat_signature(token: str, signature: str, timestamp: str, nonce: str) -> bool:
    """校验微信服务器配置签名：sha1(sort(token, timestamp, nonce))"""
    items = sorted([token or "", timestamp or "", nonce or ""])
    digest = hashlib.sha1("".join(items).encode("utf-8")).hexdigest()
    return digest == (signature or "")


def parse_wechat_message(xml_body: bytes | str) -> WechatInboundMessage | None:
    """解析微信推送 XML；空 body 返回 None。"""
    if not xml_body:
        return None
    raw = xml_body.decode("utf-8") if isinstance(xml_body, bytes) else xml_body
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    data = {child.tag: (child.text or "") for child in root}
    return WechatInboundMessage(
        msg_type=(data.get("MsgType") or "").strip().lower(),
        content=data.get("Content") or "",
        source=data.get("FromUserName") or "",
        target=data.get("ToUserName") or "",
    )


def _cdata(value: str) -> str:
    return f"<![CDATA[{(value or '').replace(']]>', '')}]]>"


def render_text_reply(message: WechatInboundMessage | None, content: str) -> str:
    """把文本回复渲染成微信 XML（收发双方对调）。"""
    source = message.source if message else ""
    target = message.target if message else ""
    return (
        "<xml>"
        f"<ToUserName>{_cdata(source)}</ToUserName>"
        f"<FromUserName>{_cdata(target)}</FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        f"<MsgType>{_cdata('text')}</MsgType>"
        f"<Content>{_cdata(content)}</Content>"
        "</xml>"
    )
