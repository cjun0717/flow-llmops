#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文件提取器（从 MinIO 加载文件 → LangChain 文档/字符串）。

迁移自 imooc internal/core/file_extractor/file_extractor.py，将 COS 下载替换为 MinIO 下载。
"""
from __future__ import annotations

import os.path
import tempfile
from pathlib import Path
from typing import Union

import requests
from langchain_community.document_loaders import (
    UnstructuredCSVLoader,
    UnstructuredExcelLoader,
    UnstructuredFileLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredPDFLoader,
    UnstructuredPowerPointLoader,
    UnstructuredXMLLoader,
    TextLoader,
)
from langchain_core.documents import Document as LCDocument
from minio import Minio

from app.config import settings
from app.models.upload_file import UploadFile


class FileExtractor:
    """文件提取器，将 MinIO 中的文件加载为 LangChain 文档或字符串"""

    def __init__(self, minio_client: Minio) -> None:
        self.minio_client = minio_client

    def load(
        self,
        upload_file: UploadFile,
        return_text: bool = False,
        is_unstructured: bool = True,
    ) -> Union[list[LCDocument], str]:
        """加载传入的 upload_file 记录，返回 LangChain 文档列表或字符串"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, os.path.basename(upload_file.key))
            self._download_from_minio(upload_file.key, file_path)
            return self.load_from_file(file_path, return_text, is_unstructured)

    def _download_from_minio(self, key: str, file_path: str) -> None:
        """从 MinIO 下载对象到本地路径"""
        self.minio_client.fget_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=key,
            file_path=file_path,
        )

    @classmethod
    def load_from_url(cls, url: str, return_text: bool = False) -> Union[list[LCDocument], str]:
        """从 URL 加载数据，返回 LangChain 文档列表或字符串"""
        response = requests.get(url, timeout=60)
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, os.path.basename(url))
            with open(file_path, "wb") as f:
                f.write(response.content)
            return cls.load_from_file(file_path, return_text)

    @classmethod
    def load_from_file(
        cls,
        file_path: str,
        return_text: bool = False,
        is_unstructured: bool = True,
    ) -> Union[list[LCDocument], str]:
        """从本地文件加载数据，返回 LangChain 文档列表或字符串"""
        delimiter = "\n\n"
        file_extension = Path(file_path).suffix.lower()

        if file_extension in [".xlsx", ".xls"]:
            loader = UnstructuredExcelLoader(file_path)
        elif file_extension == ".pdf":
            loader = UnstructuredPDFLoader(file_path)
        elif file_extension in [".md", ".markdown"]:
            loader = UnstructuredMarkdownLoader(file_path)
        elif file_extension in [".htm", ".html"]:
            loader = UnstructuredHTMLLoader(file_path)
        elif file_extension == ".csv":
            loader = UnstructuredCSVLoader(file_path)
        elif file_extension in [".ppt", ".pptx"]:
            loader = UnstructuredPowerPointLoader(file_path)
        elif file_extension == ".xml":
            loader = UnstructuredXMLLoader(file_path)
        else:
            loader = UnstructuredFileLoader(file_path) if is_unstructured else TextLoader(file_path)

        return (
            delimiter.join([doc.page_content for doc in loader.load()])
            if return_text
            else loader.load()
        )
