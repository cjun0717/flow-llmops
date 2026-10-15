#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DALL·E 图像生成客户端。

直接调用 OpenAI Images API，替代已停止维护的
langchain-community 的 DallEAPIWrapper，行为保持一致：
run(prompt) 返回以逗号分隔的图片 URL（或 b64）字符串。
未显式传入凭证时沿用 openai SDK 的默认行为（环境变量 OPENAI_API_KEY 等）。
"""
from __future__ import annotations

from typing import Any

from openai import OpenAI


class DallEAPIWrapper:
    """DALL·E Images API 薄封装。"""

    def __init__(
        self,
        model: str = "dall-e-3",
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
        separator: str = ",",
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self.model = model
        self.size = size
        self.quality = quality
        self.n = n
        self.separator = separator
        self._api_key = api_key
        self._api_base = api_base
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """延迟创建 OpenAI 客户端：构造工具时无需凭证，真正生成时才校验。"""
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key or None, base_url=self._api_base or None)
        return self._client

    def run(self, prompt: str) -> str:
        """按 prompt 生成图片，返回逗号分隔的图片地址（或 b64）字符串。"""
        try:
            response: Any = self.client.images.generate(
                model=self.model,
                prompt=prompt,
                n=self.n,
                size=self.size,
                quality=self.quality,
            )
        except Exception as e:
            raise ValueError(f"DALL·E 图片生成出错: {e}") from e
        image_urls = [image.url or image.b64_json or "" for image in response.data]
        if not image_urls:
            return ""
        return self.separator.join([url for url in image_urls if url])