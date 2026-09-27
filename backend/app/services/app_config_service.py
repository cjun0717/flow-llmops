#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用配置服务（草稿/运行时配置读取 + 校验 + LangChain 工具加载）。

迁移自 imooc app_config_service.py，同步 → async。
注意：阶段7仅实现配置读取/校验/工具加载；工作流工具(WorkflowTool)在阶段9实现，
此处 get_langchain_tools_by_workflow_ids 返回空列表占位。
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.language_model import LanguageModelManager
from app.core.tools.api_tools.entities import ToolEntity
from app.core.tools.api_tools.providers import ApiProviderManager
from app.core.tools.builtin_tools.providers import BuiltinProviderManager
from app.core.tools.mcp_tools.entities import McpToolEntity
from app.core.tools.mcp_tools.providers import McpProviderManager
from app.entities.app_entity import DEFAULT_APP_CONFIG
from app.entities.workflow_entity import WorkflowStatus
from app.lib.helper import datetime_to_timestamp, get_value_type
from app.models.app import App, AppConfig, AppConfigVersion, AppDatasetJoin
from app.models.api_tool import ApiTool, ApiToolProvider
from app.models.dataset import Dataset
from app.models.mcp_tool import McpTool, McpToolProvider
from app.models.workflow import Workflow


class AppConfigService:
    """应用配置服务"""

    def __init__(
        self,
        api_provider_manager: ApiProviderManager,
        mcp_provider_manager: McpProviderManager,
        builtin_provider_manager: BuiltinProviderManager,
        language_model_manager: LanguageModelManager,
    ) -> None:
        self.api_provider_manager = api_provider_manager
        self.mcp_provider_manager = mcp_provider_manager
        self.builtin_provider_manager = builtin_provider_manager
        self.language_model_manager = language_model_manager

    # ===== 草稿/运行时配置读取 =====

    async def get_draft_app_config(
        self, app: App, db: AsyncSession
    ) -> dict[str, Any]:
        """根据传递的应用获取该应用的草稿配置"""
        draft_app_config = await self._load_draft_config(app, db)
        if draft_app_config is None:
            raise ValueError("应用草稿配置不存在")

        validate_model_config = self._process_and_validate_model_config(
            draft_app_config.model_config
        )
        if draft_app_config.model_config != validate_model_config:
            draft_app_config.model_config = validate_model_config
            await db.commit()

        tools, validate_tools = await self._process_and_validate_tools(
            draft_app_config.tools or [], app.account_id, db
        )
        if (draft_app_config.tools or []) != validate_tools:
            draft_app_config.tools = validate_tools
            await db.commit()

        datasets, validate_datasets = await self._process_and_validate_datasets(
            draft_app_config.datasets or [], db
        )
        if set(validate_datasets) != set(draft_app_config.datasets or []):
            draft_app_config.datasets = validate_datasets
            await db.commit()

        workflows, validate_workflows = await self._process_and_validate_workflows(
            draft_app_config.workflows or [], db
        )
        if set(validate_workflows) != set(draft_app_config.workflows or []):
            draft_app_config.workflows = validate_workflows
            await db.commit()

        return self._process_and_transformer_app_config(
            validate_model_config, tools, workflows, datasets, draft_app_config
        )
    async def get_app_config(
        self, app: App, db: AsyncSession
    ) -> dict[str, Any]:
        """根据传递的应用获取该应用的运行时配置"""
        app_config = await self._load_app_config(app, db)
        if app_config is None:
            raise ValueError("应用运行时配置不存在")

        validate_model_config = self._process_and_validate_model_config(
            app_config.model_config
        )
        if app_config.model_config != validate_model_config:
            app_config.model_config = validate_model_config
            await db.commit()

        tools, validate_tools = await self._process_and_validate_tools(
            app_config.tools or [], app.account_id, db
        )
        if (app_config.tools or []) != validate_tools:
            app_config.tools = validate_tools
            await db.commit()

        # 运行时知识库走 AppDatasetJoin 表
        app_dataset_joins = await self._list_app_dataset_joins(app_config.app_id, db)
        origin_datasets = [str(j.dataset_id) for j in app_dataset_joins]
        datasets, validate_datasets = await self._process_and_validate_datasets(
            origin_datasets, db
        )
        # 删除已不存在的知识库关联
        from sqlalchemy import delete as sa_delete
        for dataset_id in (set(origin_datasets) - set(validate_datasets)):
            await db.execute(
                sa_delete(AppDatasetJoin).where(AppDatasetJoin.dataset_id == dataset_id)
            )
        await db.commit()

        workflows, validate_workflows = await self._process_and_validate_workflows(
            app_config.workflows or [], db
        )
        if set(validate_workflows) != set(app_config.workflows or []):
            app_config.workflows = validate_workflows
            await db.commit()

        return self._process_and_transformer_app_config(
            validate_model_config, tools, workflows, datasets, app_config
        )

    # ===== LangChain 工具加载（阶段8会话流式使用） =====

    async def get_langchain_tools_by_tools_config(
        self, tools_config: list[dict], db: AsyncSession
    ) -> list[BaseTool]:
        """根据传递的工具配置列表获取 langchain 工具列表"""
        tools: list[BaseTool] = []
        for tool in tools_config or []:
            tool_type = tool.get("type")
            if tool_type == "builtin_tool":
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider"]["id"], tool["tool"]["name"]
                )
                if not builtin_tool:
                    continue
                tools.append(builtin_tool(**tool["tool"].get("params", {})))
            elif tool_type == "api_tool":
                result = await db.execute(
                    select(ApiTool).where(ApiTool.id == tool["tool"]["id"])
                )
                api_tool = result.scalar_one_or_none()
                if not api_tool:
                    continue
                provider = await self._get_api_tool_provider(api_tool.provider_id, db)
                tools.append(
                    self.api_provider_manager.get_tool(
                        ToolEntity(
                            id=str(api_tool.id),
                            name=api_tool.name,
                            url=api_tool.url,
                            method=api_tool.method,
                            description=api_tool.description,
                            headers=provider.headers if isinstance(provider.headers, list) else [],
                            parameters=api_tool.parameters or [],
                        )
                    )
                )
            elif tool_type == "mcp_tool":
                result = await db.execute(
                    select(McpTool).where(McpTool.id == tool["tool"]["id"])
                )
                mcp_tool = result.scalar_one_or_none()
                if not mcp_tool:
                    continue
                provider = await self._get_mcp_tool_provider(mcp_tool.provider_id, db)
                tools.append(
                    self.mcp_provider_manager.get_tool(
                        McpToolEntity(
                            provider_id=str(provider.id),
                            name=mcp_tool.name,
                            description=mcp_tool.description,
                            url=provider.url,
                            headers=provider.headers if isinstance(provider.headers, dict) else {},
                            input_schema=mcp_tool.input_schema or {},
                            metadata=mcp_tool.tool_metadata or {},
                        )
                    )
                )
        return tools

    async def get_langchain_tools_by_workflow_ids(
        self, workflow_ids: list[UUID], db: AsyncSession
    ) -> list[BaseTool]:
        """根据传递的工作流 id 列表获取 langchain 工具列表（阶段9实现，此处占位）"""
        return []
    # ===== 私有：配置加载 =====

    @staticmethod
    async def _load_draft_config(
        app: App, db: AsyncSession
    ) -> AppConfigVersion | None:
        if app.draft_app_config_id is None:
            return None
        result = await db.execute(
            select(AppConfigVersion).where(AppConfigVersion.id == app.draft_app_config_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _load_app_config(
        app: App, db: AsyncSession
    ) -> AppConfig | None:
        if app.app_config_id is None:
            return None
        result = await db.execute(
            select(AppConfig).where(AppConfig.id == app.app_config_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _list_app_dataset_joins(
        app_id: UUID, db: AsyncSession
    ) -> list[AppDatasetJoin]:
        result = await db.execute(
            select(AppDatasetJoin).where(AppDatasetJoin.app_id == app_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def _get_api_tool_provider(provider_id: UUID, db: AsyncSession) -> ApiToolProvider:
        result = await db.execute(
            select(ApiToolProvider).where(ApiToolProvider.id == provider_id)
        )
        return result.scalar_one()

    @staticmethod
    async def _get_mcp_tool_provider(provider_id: UUID, db: AsyncSession) -> McpToolProvider:
        result = await db.execute(
            select(McpToolProvider).where(McpToolProvider.id == provider_id)
        )
        return result.scalar_one()

    # ===== 私有：配置转换 =====

    @classmethod
    def _process_and_transformer_app_config(
        cls,
        model_config: dict[str, Any],
        tools: list[dict],
        workflows: list[dict],
        datasets: list[dict],
        app_config: AppConfig | AppConfigVersion,
    ) -> dict[str, Any]:
        return {
            "id": str(app_config.id),
            "model_config": model_config,
            "dialog_round": app_config.dialog_round,
            "preset_prompt": app_config.preset_prompt,
            "tools": tools,
            "workflows": workflows,
            "datasets": datasets,
            "retrieval_config": app_config.retrieval_config,
            "long_term_memory": app_config.long_term_memory,
            "opening_statement": app_config.opening_statement,
            "opening_questions": app_config.opening_questions,
            "speech_to_text": app_config.speech_to_text,
            "text_to_speech": app_config.text_to_speech,
            "suggested_after_answer": app_config.suggested_after_answer,
            "review_config": app_config.review_config,
            "updated_at": datetime_to_timestamp(app_config.updated_at),
            "created_at": datetime_to_timestamp(app_config.created_at),
        }
    # ===== 私有：工具校验 =====

    async def _process_and_validate_tools(
        self, origin_tools: list[dict], account_id: UUID, db: AsyncSession
    ) -> tuple[list[dict], list[dict]]:
        validate_tools: list[dict] = []
        tools: list[dict] = []
        for tool in origin_tools or []:
            tool_type = tool.get("type")
            if tool_type == "builtin_tool":
                provider = self.builtin_provider_manager.get_provider(tool["provider_id"])
                if provider is None:
                    continue
                tool_entity = provider.get_tool_entity(tool["tool_id"])
                if tool_entity is None:
                    continue
                param_keys = {param.name for param in tool_entity.params}
                params = tool.get("params", {})
                if set(params.keys()) - param_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }
                validate_tools.append({**tool, "params": params})
                provider_entity = provider.provider_entity
                tools.append({
                    "type": "builtin_tool",
                    "provider": {
                        "id": provider_entity.name,
                        "name": provider_entity.name,
                        "label": provider_entity.label,
                        "icon": f"/api/v1/builtin-tools/{provider_entity.name}/icon",
                        "description": provider_entity.description,
                    },
                    "tool": {
                        "id": tool_entity.name,
                        "name": tool_entity.name,
                        "label": tool_entity.label,
                        "description": tool_entity.description,
                        "params": tool.get("params", {}),
                    },
                })
            elif tool_type == "api_tool":
                result = await db.execute(
                    select(ApiTool).where(
                        ApiTool.provider_id == tool["provider_id"],
                        ApiTool.name == tool["tool_id"],
                        ApiTool.account_id == account_id,
                    )
                )
                tool_record = result.scalar_one_or_none()
                if not tool_record:
                    continue
                validate_tools.append(tool)
                provider = await self._get_api_tool_provider(tool_record.provider_id, db)
                tools.append({
                    "type": "api_tool",
                    "provider": {
                        "id": str(provider.id),
                        "name": provider.name,
                        "label": provider.name,
                        "icon": provider.icon,
                        "description": provider.description,
                    },
                    "tool": {
                        "id": str(tool_record.id),
                        "name": tool_record.name,
                        "label": tool_record.name,
                        "description": tool_record.description,
                        "params": {},
                    },
                })
            elif tool_type == "mcp_tool":
                result = await db.execute(
                    select(McpTool).where(
                        McpTool.provider_id == tool["provider_id"],
                        McpTool.name == tool["tool_id"],
                        McpTool.account_id == account_id,
                    )
                )
                tool_record = result.scalar_one_or_none()
                if not tool_record:
                    continue
                validate_tools.append({**tool, "params": {}})
                provider = await self._get_mcp_tool_provider(tool_record.provider_id, db)
                tools.append({
                    "type": "mcp_tool",
                    "provider": {
                        "id": str(provider.id),
                        "name": provider.name,
                        "label": provider.name,
                        "icon": "",
                        "description": provider.description,
                    },
                    "tool": {
                        "id": str(tool_record.id),
                        "name": tool_record.name,
                        "label": tool_record.name,
                        "description": tool_record.description,
                        "params": {},
                    },
                })
        return tools, validate_tools
    # ===== 私有：知识库校验 =====

    @staticmethod
    async def _process_and_validate_datasets(
        origin_datasets: list, db: AsyncSession
    ) -> tuple[list[dict], list[str]]:
        origin_datasets = [str(d) for d in (origin_datasets or [])]
        if not origin_datasets:
            return [], []
        result = await db.execute(select(Dataset).where(Dataset.id.in_(origin_datasets)))
        dataset_records = list(result.scalars().all())
        dataset_dict = {str(r.id): r for r in dataset_records}
        dataset_sets = set(dataset_dict.keys())
        validate_datasets = [d for d in origin_datasets if d in dataset_sets]
        datasets = []
        for dataset_id in validate_datasets:
            dataset = dataset_dict[dataset_id]
            datasets.append({
                "id": str(dataset.id),
                "name": dataset.name,
                "icon": dataset.icon,
                "description": dataset.description,
            })
        return datasets, validate_datasets

    # ===== 私有：工作流校验 =====

    @staticmethod
    async def _process_and_validate_workflows(
        origin_workflows: list, db: AsyncSession
    ) -> tuple[list[dict], list[str]]:
        origin_workflows = [str(w) for w in (origin_workflows or [])]
        if not origin_workflows:
            return [], []
        result = await db.execute(
            select(Workflow).where(
                Workflow.id.in_(origin_workflows),
                Workflow.status == WorkflowStatus.PUBLISHED,
            )
        )
        workflow_records = list(result.scalars().all())
        workflow_dict = {str(r.id): r for r in workflow_records}
        workflow_sets = set(workflow_dict.keys())
        validate_workflows = [w for w in origin_workflows if w in workflow_sets]
        workflows = []
        for workflow_id in validate_workflows:
            workflow = workflow_dict[workflow_id]
            workflows.append({
                "id": str(workflow.id),
                "name": workflow.name,
                "icon": workflow.icon,
                "description": workflow.description,
            })
        return workflows, validate_workflows

    # ===== 私有：model_config 校验 =====

    def _process_and_validate_model_config(
        self, origin_model_config: Any
    ) -> dict[str, Any]:
        if not isinstance(origin_model_config, dict):
            return DEFAULT_APP_CONFIG["model_config"]

        model_config = {
            "provider": origin_model_config.get("provider", ""),
            "model": origin_model_config.get("model", ""),
            "parameters": origin_model_config.get("parameters", {}),
        }

        if not model_config["provider"] or not isinstance(model_config["provider"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        try:
            provider = self.language_model_manager.get_provider(model_config["provider"])
        except Exception:
            return DEFAULT_APP_CONFIG["model_config"]
        if provider is None:
            return DEFAULT_APP_CONFIG["model_config"]

        if not model_config["model"] or not isinstance(model_config["model"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        try:
            model_entity = provider.get_model_entity(model_config["model"])
        except Exception:
            return DEFAULT_APP_CONFIG["model_config"]
        if model_entity is None:
            return DEFAULT_APP_CONFIG["model_config"]

        if not isinstance(model_config["parameters"], dict):
            model_config["parameters"] = {
                parameter.name: parameter.default for parameter in model_entity.parameters
            }

        parameters = {}
        for parameter in model_entity.parameters:
            parameter_value = model_config["parameters"].get(parameter.name, parameter.default)
            if parameter.required:
                if parameter_value is None:
                    parameter_value = parameter.default
                else:
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default
            else:
                if parameter_value is not None:
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default
            if parameter.options and parameter_value not in parameter.options:
                parameter_value = parameter.default
            from app.core.language_model.entities.model_entity import ModelParameterType
            if parameter.type in [ModelParameterType.INT, ModelParameterType.FLOAT] and parameter_value is not None:
                if (parameter.min and parameter_value < parameter.min) or (parameter.max and parameter_value > parameter.max):
                    parameter_value = parameter.default
            parameters[parameter.name] = parameter_value

        model_config["parameters"] = parameters
        return model_config
