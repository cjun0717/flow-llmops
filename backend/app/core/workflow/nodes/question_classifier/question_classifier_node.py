#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""问题分类器节点（迁移自 imooc question_classifier_node.py）。

适配 FastAPI：使用项目默认语言模型（通过 lru_cache 单例访问器获取）替代硬编码 ChatOpenAI。
作为 LangGraph 条件边函数，invoke 返回下一节点标识字符串。
"""
from __future__ import annotations

import json
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END

from app.core.workflow.entities.workflow_entity import WorkflowState
from app.core.workflow.nodes.base_node import BaseNode
from app.core.workflow.utils.helper import extract_variables_from_state
from .question_classifier_entity import (
    QuestionClassifierNodeData,
    QUESTION_CLASSIFIER_SYSTEM_PROMPT,
)


class QuestionClassifierNode(BaseNode):
    """问题分类器节点"""
    node_data: QuestionClassifierNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> str:
        """执行问题分类后返回下一节点标识，LLM 判断错误时默认返回第一个节点名称"""
        # 1.提取节点输入变量字典
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2.构建问题分类提示 prompt 模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", QUESTION_CLASSIFIER_SYSTEM_PROMPT),
            ("human", "{query}"),
        ])

        # 3.通过 lru_cache 单例访问器加载默认语言模型
        from app.deps import get_language_model_manager
        from app.services.language_model_service import LanguageModelService

        language_model_service = LanguageModelService(get_language_model_manager())
        llm = language_model_service.load_default_language_model()

        # 4.构建分类链
        chain = prompt | llm | StrOutputParser()

        # 5.获取分类调用结果
        node_flag = chain.invoke({
            "preset_classes": json.dumps(
                [
                    {
                        "query": class_config.query,
                        "class": f"qc_source_handle_{str(class_config.source_handle_id)}"
                    } for class_config in self.node_data.classes
                ]
            ),
            "query": inputs_dict.get("query", "用户没有输入任何内容")
        })

        # 6.获取所有分类信息
        all_classes = [f"qc_source_handle_{str(item.source_handle_id)}" for item in self.node_data.classes]

        # 7.校验分类标识
        if len(all_classes) == 0:
            node_flag = END
        elif node_flag not in all_classes:
            node_flag = all_classes[0]

        return node_flag
