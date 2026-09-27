#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流工具函数（迁移自 imooc workflow/utils/helper.py）。"""
from __future__ import annotations

from typing import Any

from app.core.workflow.entities.variable_entity import (
    VARIABLE_TYPE_DEFAULT_VALUE_MAP,
    VARIABLE_TYPE_MAP,
    VariableEntity,
    VariableValueType,
)
from app.core.workflow.entities.workflow_entity import WorkflowState


def extract_variables_from_state(variables: list[VariableEntity], state: WorkflowState) -> dict[str, Any]:
    """从状态中提取变量映射值信息"""
    variables_dict = {}

    for variable in variables:
        # 1.获取变量类型类
        variable_type_cls = VARIABLE_TYPE_MAP.get(variable.type)

        # 2.判断数据是引用还是直接输入
        if variable.value.type == VariableValueType.LITERAL:
            variables_dict[variable.name] = variable_type_cls(variable.value.content)
        else:
            # 3.引用 or 生成类型，遍历节点获取数据
            for node_result in state["node_results"]:
                if node_result.node_data.id == variable.value.content.ref_node_id:
                    variables_dict[variable.name] = variable_type_cls(
                        node_result.outputs.get(
                            variable.value.content.ref_var_name,
                            VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(variable.type),
                        )
                    )
    return variables_dict
