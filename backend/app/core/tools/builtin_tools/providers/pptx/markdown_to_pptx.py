#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Markdown 转 PPT 工具（python-pptx + mistune，输出上传至 MinIO）。"""
from __future__ import annotations

import logging
import os
import tempfile
import urllib.request
import uuid
from typing import Any, Optional

import mistune
from langchain_core.tools import BaseTool
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Length, Pt
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class PPTRenderer(mistune.HTMLRenderer):
    """借助 HTML 渲染器重写并定义 PPT 渲染器"""

    prs: Presentation
    font_name: str
    image_folder: str
    content_left: Length
    content_top: Length
    content_width: Length
    line_height: Length

    def __init__(self, prs: Presentation, image_folder: str) -> None:
        super().__init__()
        self.prs = prs
        self.current_slide = None
        self.font_name = "微软雅黑"
        self.image_folder = image_folder
        self.content_left = Inches(1)
        self.content_top = Inches(1.5)
        self.content_width = Inches(8.5)
        self.line_height = Pt(24)

    def heading(self, text: str, level: int, **attrs: Any) -> str:
        if level == 1:
            slide = self.prs.slides.add_slide(self.prs.slide_layouts[0])
            title = slide.shapes.title
            sub_title = slide.placeholders[1]
            title.text = text.strip()
            title.text_frame.paragraphs[0].font.name = self.font_name
            sub_title.text = "由慕课LLMOps平台生成"
            self.current_slide = None
        else:
            slide_layout = self.prs.slide_layouts[5]
            self.current_slide = self.prs.slides.add_slide(slide_layout)
            title_shape = self.current_slide.shapes.title
            title_shape.text = text.strip()
            title_shape.text_frame.paragraphs[0].font.name = self.font_name
            self.content_top = Inches(1.5)
        return ""

    def paragraph(self, text: str) -> str:
        text = text.strip()
        if self.current_slide and len(text):
            self.check_new_slide()
            text_height = self.estimate_text_height(text, font_size=18)
            text_box = self.current_slide.shapes.add_textbox(
                self.content_left, self.content_top, self.content_width, text_height
            )
            tf = text_box.text_frame
            tf.word_wrap = True
            if tf.paragraphs:
                tf.paragraphs[0]._element.getparent().remove(tf.paragraphs[0]._element)
            p = tf.add_paragraph()
            p.text = text
            p.font.name = self.font_name
            p.font.size = Pt(18)
            self.content_top += text_height
        return ""

    def list(self, text: str, ordered: bool, **attrs: Any) -> str:
        if self.current_slide:
            self.check_new_slide()
            text_box = self.current_slide.shapes.add_textbox(
                self.content_left, self.content_top, self.content_width, Inches(4)
            )
            tf = text_box.text_frame
            tf.word_wrap = True
            tf.clear()
            items = text.strip().split("\n")
            total_height = 0
            for item in items:
                self.check_new_slide()
                p = tf.add_paragraph()
                p.text = item.strip().replace("<li>", "").replace("</li>", "")
                p.level = 0
                p.font.name = self.font_name
                p.font.size = Pt(18)
                item_height = self.estimate_text_height(item, font_size=18)
                total_height += item_height
                self.content_top += item_height
            if total_height > Inches(4):
                self.check_new_slide()
        return ""

    def image(self, text: str, url: str, title: Optional[str] = None) -> str:
        try:
            if self.current_slide:
                self.check_new_slide()
                if url.startswith("http"):
                    local_path = os.path.join(self.image_folder, os.path.basename(url))
                    urllib.request.urlretrieve(url, local_path)
                else:
                    local_path = url
                pic = self.current_slide.shapes.add_picture(
                    local_path,
                    (self.prs.slide_width - Inches(4)) / 2,
                    self.content_top,
                    width=Inches(4),
                )
                self.content_top += pic.height + Inches(0.5)
        except Exception as error:
            logger.error("PPTRenderer图片处理失败: %s", error, exc_info=True)
        return ""

    def block_code(self, code: str, info: Optional[str] = None) -> str:
        if self.current_slide:
            self.check_new_slide()
            text_box = self.current_slide.shapes.add_textbox(
                self.content_left, self.content_top, self.content_width, Inches(2)
            )
            tf = text_box.text_frame
            p = tf.add_paragraph()
            p.text = code.strip()
            p.font.name = "Consolas"
            p.font.size = Pt(14)
            p.font.color.rgb = RGBColor(0x33, 0x66, 0x99)
            self.content_top += self.line_height * (code.count("\n") + 2)
        return ""

    def check_new_slide(self) -> None:
        if self.content_top >= Inches(6):
            title = ""
            if self.current_slide:
                title_shape = self.current_slide.shapes.title
                if title_shape and title_shape.text:
                    title = title_shape.text
            self.current_slide = self.prs.slides.add_slide(self.prs.slide_layouts[5])
            self.content_top = Inches(1.5)
            if title:
                new_title_shape = self.current_slide.shapes.title
                if new_title_shape:
                    new_title_shape.text = title
                    new_title_shape.text_frame.paragraphs[0].font.name = self.font_name

    @classmethod
    def estimate_text_height(
        cls, text: str, font_size: int = 20, avg_char_per_line: int = 30
    ) -> float:
        lines = max(1, (len(text) // avg_char_per_line) + text.count("\n"))
        line_height = Pt(font_size * 1.2)
        return (lines + 0.3) * line_height


class MarkdownToPPTXArgsSchema(BaseModel):
    markdown: str = Field(description="要生成PPT内容的markdown文档字符串。")


def _upload_to_minio(filepath: str, filename: str) -> str:
    """将生成的 pptx 上传到 MinIO 并返回可访问 URL"""
    from app.config import settings
    from app.deps import get_minio_client
    from app.services.upload_file_service import UploadFileService

    client = get_minio_client()
    UploadFileService.ensure_bucket(client)
    key = f"builtin-tools/markdown-to-pptx/{filename}"
    with open(filepath, "rb") as f:
        client.put_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=key,
            data=f,
            length=os.path.getsize(filepath),
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    return UploadFileService.get_file_url(key)


class MarkdownToPPTXTool(BaseTool):
    """markdown 转本地 pptx 工具"""

    name: str = "markdown_to_pptx"
    description: str = (
        "这是一个可以将markdown文本转换成PPT的工具，传递的参数是markdown对应的文本字符串，"
        "返回的数据是PPT的下载地址。"
    )
    args_schema: type[BaseModel] = MarkdownToPPTXArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                prs = Presentation()
                renderer = PPTRenderer(prs, temp_dir)
                markdown = mistune.Markdown(renderer)
                markdown(kwargs.get("markdown"))

                filename = str(uuid.uuid4()) + ".pptx"
                filepath = os.path.join(temp_dir, filename)
                prs.save(filepath)

                return _upload_to_minio(filepath, filename)
        except Exception as error:
            logger.error("markdown_to_pptx出错: %s", error, exc_info=True)
            return f"生成PPT演示文稿失败，错误原因: {str(error)}"


def markdown_to_pptx(**kwargs) -> BaseTool:
    """一个可以将 markdown 文本转换成 PPT 的工具"""
    return MarkdownToPPTXTool()
