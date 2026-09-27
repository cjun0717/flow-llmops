#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Python代码运行节点（迁移自 imooc code_node.py）。"""
from __future__ import annotations

import ast
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.core.workflow.entities.node_entity import NodeResult, NodeStatus
from app.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from app.core.workflow.entities.workflow_entity import WorkflowState
from app.core.workflow.nodes.base_node import BaseNode
from app.core.workflow.utils.helper import extract_variables_from_state
from app.exceptions import FailException
from .code_entity import CodeNodeData


class CodeNode(BaseNode):
    """Python代码运行节点"""
    node_data: CodeNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """执行代码函数名字必须为 main，参数名为 params，有且只有一个参数"""
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # todo: 执行任意 Python 代码有安全风险，后期需迁移到沙箱/容器中运行
        result = self._execute_function(self.node_data.code, params=inputs_dict)

        if not isinstance(result, dict):
            raise FailException("main函数的返回值必须是一个字典")

        outputs_dict = {}
        outputs = self.node_data.outputs
        for output in outputs:
            outputs_dict[output.name] = result.get(
                output.name,
                VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(output.type),
            )

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs_dict,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }

    @classmethod
    def _execute_function(cls, code: str, *args, **kwargs):
        """执行Python函数代码"""
        try:
            # 1.解析代码为 AST
            tree = ast.parse(code)

            # 2.查找 main 函数
            main_func = None
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    if node.name == "main":
                        if main_func:
                            raise FailException("代码中只能有一个main函数")
                        if len(node.args.args) != 1 or node.args.args[0].arg != "params":
                            raise FailException("main函数必须只有一个参数，且参数为params")
                        main_func = node
                    else:
                        raise FailException("代码中不能包含其他函数，只能有main函数")
                else:
                    raise FailException("代码中只能包含函数定义，不允许其他语句存在")

            if not main_func:
                raise FailException("代码中必须包含名为main的函数")

            # 3.通过 AST 校验后执行代码
            local_vars = {}
            exec(code, {}, local_vars)

            if "main" in local_vars and callable(local_vars["main"]):
                return local_vars["main"](*args, **kwargs)
            else:
                raise FailException("main函数必须是一个可调用的函数")
        except Exception as e:
            raise FailException("Python代码执行出错")
