#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档加载器（薄封装 unstructured 库，接口对齐 LangChain BaseLoader）。

替代已停止维护的 langchain_community.document_loaders 的 Unstructured 系列：
按扩展名分派到 unstructured 对应的 partition 函数，与原实现一致地
将全部元素合并为单个 Document（等价原 mode="single"）。
"""
from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Iterator

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document


class _UnstructuredLoader(BaseLoader):
    """基于 unstructured 库的通用文档提取器。

    子类通过 `_partition_func` 声明 unstructured 的分区函数
    （格式 "模块路径:函数名"），延迟导入避免拖慢应用启动。
    """

    _partition_func: str = "unstructured.partition.auto:partition"

    def __init__(self, file_path: str, mode: str = "single") -> None:
        self.file_path = file_path
        if mode not in ("single", "elements"):
            raise ValueError(f"不支持的 mode: {mode}，仅支持 single / elements")
        self.mode = mode

    def _load_partition(self) -> Callable[..., Any]:
        module_path, func_name = self._partition_func.rsplit(":", 1)
        return getattr(import_module(module_path), func_name)

    def lazy_load(self) -> Iterator[Document]:
        """惰性加载文档。single 模式合并为单个 Document，elements 模式逐元素返回。"""
        partition = self._load_partition()
        elements = partition(filename=self.file_path)
        if self.mode == "single":
            texts = [str(element) for element in elements]
            yield Document(
                page_content="\n\n".join(texts),
                metadata={"source": self.file_path},
            )
            return
        for element in elements:
            yield Document(page_content=str(element), metadata={"source": self.file_path})


class UnstructuredFileLoader(_UnstructuredLoader):
    """通用文档提取（unstructured partition.auto 自动识别格式）。"""

    _partition_func = "unstructured.partition.auto:partition"


class UnstructuredExcelLoader(_UnstructuredLoader):
    """Excel 文档提取（依赖 openpyxl）。"""

    _partition_func = "unstructured.partition.xlsx:partition_xlsx"


class UnstructuredPDFLoader(_UnstructuredLoader):
    """PDF 文档提取（依赖 pdfminer.six）。"""

    _partition_func = "unstructured.partition.pdf:partition_pdf"


class UnstructuredMarkdownLoader(_UnstructuredLoader):
    """Markdown 文档提取。"""

    _partition_func = "unstructured.partition.md:partition_md"


class UnstructuredHTMLLoader(_UnstructuredLoader):
    """HTML 文档提取。"""

    _partition_func = "unstructured.partition.html:partition_html"


class UnstructuredCSVLoader(_UnstructuredLoader):
    """CSV 文档提取。"""

    _partition_func = "unstructured.partition.csv:partition_csv"


class UnstructuredPowerPointLoader(_UnstructuredLoader):
    """PPT 文档提取（依赖 python-pptx）。"""

    _partition_func = "unstructured.partition.pptx:partition_pptx"


class UnstructuredXMLLoader(_UnstructuredLoader):
    """XML 文档提取。"""

    _partition_func = "unstructured.partition.xml:partition_xml"


class TextLoader(BaseLoader):
    """纯文本加载器（等价原 community 的 TextLoader，默认 utf-8）。"""

    def __init__(self, file_path: str, encoding: str = "utf-8") -> None:
        self.file_path = file_path
        self.encoding = encoding

    def lazy_load(self) -> Iterator[Document]:
        with open(self.file_path, encoding=self.encoding) as f:
            text = f.read()
        yield Document(page_content=text, metadata={"source": self.file_path})