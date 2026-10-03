#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用草稿配置校验器（迁移自 imooc AppService._validate_draft_app_config）。

独立成模块以便控制长度，由 AppService 调用。
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.audio_entity import ALLOWED_AUDIO_VOICES
from app.entities.workflow_entity import WorkflowStatus
from app.exceptions import ValidateException
from app.models.account import Account
from app.models.api_tool import ApiTool
from app.models.dataset import Dataset
from app.models.mcp_tool import McpTool
from app.models.workflow import Workflow
from app.models.user_model import UserModel, UserModelType
from app.services.app_config_service import AppConfigService
from app.services.user_model_service import sanitize_chat_parameters


ACCEPTABLE_FIELDS = [
    "model_config", "dialog_round", "preset_prompt",
    "tools", "workflows", "datasets", "retrieval_config",
    "long_term_memory", "opening_statement", "opening_questions",
    "speech_to_text", "text_to_speech", "suggested_after_answer", "review_config",
]


async def validate_draft_app_config(
    draft_app_config: dict[str, Any],
    account: Account,
    db: AsyncSession,
    app_config_service: AppConfigService,
) -> dict[str, Any]:
    """校验传递的应用草稿配置信息，返回校验后的数据。"""
    if (
        not draft_app_config
        or not isinstance(draft_app_config, dict)
        or set(draft_app_config.keys()) - set(ACCEPTABLE_FIELDS)
    ):
        raise ValidateException("草稿配置字段出错，请核实后重试")

    await _validate_model_config(draft_app_config, account, db)
    _validate_dialog_round(draft_app_config)
    _validate_preset_prompt(draft_app_config)
    await _validate_tools(draft_app_config, account, db, app_config_service)
    await _validate_workflows(draft_app_config, account, db)
    await _validate_datasets(draft_app_config, account, db)
    _validate_retrieval_config(draft_app_config)
    _validate_long_term_memory(draft_app_config)
    _validate_opening_statement(draft_app_config)
    _validate_opening_questions(draft_app_config)
    _validate_speech_to_text(draft_app_config)
    _validate_text_to_speech(draft_app_config)
    _validate_suggested_after_answer(draft_app_config)
    _validate_review_config(draft_app_config)

    return draft_app_config


async def _validate_model_config(
    draft_app_config: dict, account: Account, db: AsyncSession
) -> None:
    if "model_config" not in draft_app_config:
        return
    model_config = draft_app_config["model_config"]
    if not isinstance(model_config, dict):
        raise ValidateException("模型配置格式错误，请核实后重试")
    if set(model_config.keys()) != {"user_model_id", "parameters"}:
        raise ValidateException("模型键配置格式错误，请核实后重试")
    user_model_id = model_config.get("user_model_id") or ""
    if user_model_id:
        if not isinstance(user_model_id, str):
            raise ValidateException("对话模型无效，请先在模型管理中添加")
        try:
            uid = UUID(user_model_id)
        except Exception as exc:
            raise ValidateException("对话模型无效，请先在模型管理中添加") from exc
        record = await db.get(UserModel, uid)
        if (
            record is None
            or record.account_id != account.id
            or record.model_type != UserModelType.CHAT
        ):
            raise ValidateException("对话模型无效，请先在模型管理中添加")
    model_config["parameters"] = sanitize_chat_parameters(model_config.get("parameters"))
    draft_app_config["model_config"] = model_config


def _validate_dialog_round(draft_app_config: dict) -> None:
    if "dialog_round" not in draft_app_config:
        return
    dialog_round = draft_app_config["dialog_round"]
    if not isinstance(dialog_round, int) or not (0 <= dialog_round <= 100):
        raise ValidateException("携带上下文轮数范围为0-100")


def _validate_preset_prompt(draft_app_config: dict) -> None:
    if "preset_prompt" not in draft_app_config:
        return
    preset_prompt = draft_app_config["preset_prompt"]
    if not isinstance(preset_prompt, str) or len(preset_prompt) > 2000:
        raise ValidateException("人设与回复逻辑必须是字符串，长度在0-2000个字符")


async def _validate_tools(
    draft_app_config: dict, account: Account, db: AsyncSession, app_config_service: AppConfigService
) -> None:
    if "tools" not in draft_app_config:
        return
    tools = draft_app_config["tools"]
    validate_tools: list[dict] = []
    if not isinstance(tools, list):
        raise ValidateException("工具列表必须是列表型数据")
    if len(tools) > 5:
        raise ValidateException("Agent绑定的工具数不能超过5")
    for tool in tools:
        if not tool or not isinstance(tool, dict):
            raise ValidateException("绑定插件工具参数出错")
        if set(tool.keys()) != {"type", "provider_id", "tool_id", "params"}:
            raise ValidateException("绑定插件工具参数出错")
        if tool["type"] not in ["builtin_tool", "api_tool", "mcp_tool"]:
            raise ValidateException("绑定插件工具参数出错")
        if (
            not tool["provider_id"]
            or not tool["tool_id"]
            or not isinstance(tool["provider_id"], str)
            or not isinstance(tool["tool_id"], str)
        ):
            raise ValidateException("插件提供者或者插件标识参数出错")
        if not isinstance(tool["params"], dict):
            raise ValidateException("插件自定义参数格式错误")
        if tool["type"] == "builtin_tool":
            builtin_tool = app_config_service.builtin_provider_manager.get_tool(
                tool["provider_id"], tool["tool_id"]
            )
            if not builtin_tool:
                continue
        elif tool["type"] == "api_tool":
            result = await db.execute(
                select(ApiTool).where(
                    ApiTool.provider_id == tool["provider_id"],
                    ApiTool.name == tool["tool_id"],
                    ApiTool.account_id == account.id,
                )
            )
            if not result.scalar_one_or_none():
                continue
        else:
            result = await db.execute(
                select(McpTool).where(
                    McpTool.provider_id == tool["provider_id"],
                    McpTool.name == tool["tool_id"],
                    McpTool.account_id == account.id,
                )
            )
            if not result.scalar_one_or_none():
                continue
        validate_tools.append(tool)
    check_tools = [f"{t['provider_id']}_{t['tool_id']}" for t in validate_tools]
    if len(set(check_tools)) != len(validate_tools):
        raise ValidateException("绑定插件存在重复")
    draft_app_config["tools"] = validate_tools


async def _validate_workflows(draft_app_config: dict, account: Account, db: AsyncSession) -> None:
    if "workflows" not in draft_app_config:
        return
    workflows = draft_app_config["workflows"]
    if not isinstance(workflows, list):
        raise ValidateException("绑定工作流列表参数格式错误")
    if len(workflows) > 5:
        raise ValidateException("Agent绑定的工作流数量不能超过5个")
    for workflow_id in workflows:
        try:
            UUID(workflow_id)
        except Exception:
            raise ValidateException("工作流参数必须是UUID")
    if len(set(workflows)) != len(workflows):
        raise ValidateException("绑定工作流存在重复")
    result = await db.execute(
        select(Workflow).where(
            Workflow.id.in_(workflows),
            Workflow.account_id == account.id,
            Workflow.status == WorkflowStatus.PUBLISHED,
        )
    )
    workflow_records = result.scalars().all()
    workflow_sets = {str(r.id) for r in workflow_records}
    draft_app_config["workflows"] = [w for w in workflows if w in workflow_sets]


async def _validate_datasets(draft_app_config: dict, account: Account, db: AsyncSession) -> None:
    if "datasets" not in draft_app_config:
        return
    datasets = draft_app_config["datasets"]
    if not isinstance(datasets, list):
        raise ValidateException("绑定知识库列表参数格式错误")
    if len(datasets) > 5:
        raise ValidateException("Agent绑定的知识库数量不能超过5个")
    for dataset_id in datasets:
        try:
            UUID(dataset_id)
        except Exception:
            raise ValidateException("知识库列表参数必须是UUID")
    if len(set(datasets)) != len(datasets):
        raise ValidateException("绑定知识库存在重复")
    result = await db.execute(
        select(Dataset).where(
            Dataset.id.in_(datasets),
            Dataset.account_id == account.id,
        )
    )
    dataset_records = result.scalars().all()
    dataset_sets = {str(r.id) for r in dataset_records}
    draft_app_config["datasets"] = [d for d in datasets if d in dataset_sets]


def _validate_retrieval_config(draft_app_config: dict) -> None:
    if "retrieval_config" not in draft_app_config:
        return
    retrieval_config = draft_app_config["retrieval_config"]
    if not retrieval_config or not isinstance(retrieval_config, dict):
        raise ValidateException("检索配置格式错误")
    if set(retrieval_config.keys()) != {"retrieval_strategy", "k", "score"}:
        raise ValidateException("检索配置格式错误")
    if retrieval_config["retrieval_strategy"] not in ["semantic", "full_text", "hybrid"]:
        raise ValidateException("检测策略格式错误")
    if not isinstance(retrieval_config["k"], int) or not (0 <= retrieval_config["k"] <= 10):
        raise ValidateException("最大召回数量范围为0-10")
    if not isinstance(retrieval_config["score"], float) or not (0 <= retrieval_config["score"] <= 1):
        raise ValidateException("最小匹配范围为0-1")


def _validate_long_term_memory(draft_app_config: dict) -> None:
    if "long_term_memory" not in draft_app_config:
        return
    long_term_memory = draft_app_config["long_term_memory"]
    if not long_term_memory or not isinstance(long_term_memory, dict):
        raise ValidateException("长期记忆设置格式错误")
    if set(long_term_memory.keys()) != {"enable"} or not isinstance(long_term_memory["enable"], bool):
        raise ValidateException("长期记忆设置格式错误")


def _validate_opening_statement(draft_app_config: dict) -> None:
    if "opening_statement" not in draft_app_config:
        return
    opening_statement = draft_app_config["opening_statement"]
    if not isinstance(opening_statement, str) or len(opening_statement) > 2000:
        raise ValidateException("对话开场白的长度范围是0-2000")


def _validate_opening_questions(draft_app_config: dict) -> None:
    if "opening_questions" not in draft_app_config:
        return
    opening_questions = draft_app_config["opening_questions"]
    if not isinstance(opening_questions, list) or len(opening_questions) > 3:
        raise ValidateException("开场建议问题不能超过3个")
    for opening_question in opening_questions:
        if not isinstance(opening_question, str):
            raise ValidateException("开场建议问题必须是字符串")


def _validate_speech_to_text(draft_app_config: dict) -> None:
    if "speech_to_text" not in draft_app_config:
        return
    speech_to_text = draft_app_config["speech_to_text"]
    if not speech_to_text or not isinstance(speech_to_text, dict):
        raise ValidateException("语音转文本设置格式错误")
    if set(speech_to_text.keys()) != {"enable"} or not isinstance(speech_to_text["enable"], bool):
        raise ValidateException("语音转文本设置格式错误")


def _validate_text_to_speech(draft_app_config: dict) -> None:
    if "text_to_speech" not in draft_app_config:
        return
    text_to_speech = draft_app_config["text_to_speech"]
    if not isinstance(text_to_speech, dict):
        raise ValidateException("文本转语音设置格式错误")
    if (
        set(text_to_speech.keys()) != {"enable", "voice", "auto_play"}
        or not isinstance(text_to_speech["enable"], bool)
        or text_to_speech["voice"] not in ALLOWED_AUDIO_VOICES
        or not isinstance(text_to_speech["auto_play"], bool)
    ):
        raise ValidateException("文本转语音设置格式错误")


def _validate_suggested_after_answer(draft_app_config: dict) -> None:
    if "suggested_after_answer" not in draft_app_config:
        return
    suggested_after_answer = draft_app_config["suggested_after_answer"]
    if not suggested_after_answer or not isinstance(suggested_after_answer, dict):
        raise ValidateException("回答后建议问题设置格式错误")
    if set(suggested_after_answer.keys()) != {"enable"} or not isinstance(suggested_after_answer["enable"], bool):
        raise ValidateException("回答后建议问题设置格式错误")


def _validate_review_config(draft_app_config: dict) -> None:
    if "review_config" not in draft_app_config:
        return
    review_config = draft_app_config["review_config"]
    if not review_config or not isinstance(review_config, dict):
        raise ValidateException("审核配置格式错误")
    if set(review_config.keys()) != {"enable", "keywords", "inputs_config", "outputs_config"}:
        raise ValidateException("审核配置格式错误")
    if not isinstance(review_config["enable"], bool):
        raise ValidateException("review.enable格式错误")
    if (
        not isinstance(review_config["keywords"], list)
        or (review_config["enable"] and len(review_config["keywords"]) == 0)
        or len(review_config["keywords"]) > 100
    ):
        raise ValidateException("review.keywords非空且不能超过100个关键词")
    for keyword in review_config["keywords"]:
        if not isinstance(keyword, str):
            raise ValidateException("review.keywords敏感词必须是字符串")
    if (
        not review_config["inputs_config"]
        or not isinstance(review_config["inputs_config"], dict)
        or set(review_config["inputs_config"].keys()) != {"enable", "preset_response"}
        or not isinstance(review_config["inputs_config"]["enable"], bool)
        or not isinstance(review_config["inputs_config"]["preset_response"], str)
    ):
        raise ValidateException("review.inputs_config必须是一个字典")
    if (
        not review_config["outputs_config"]
        or not isinstance(review_config["outputs_config"], dict)
        or set(review_config["outputs_config"].keys()) != {"enable"}
        or not isinstance(review_config["outputs_config"]["enable"], bool)
    ):
        raise ValidateException("review.outputs_config格式错误")
    if review_config["enable"]:
        if (
            review_config["inputs_config"]["enable"] is False
            and review_config["outputs_config"]["enable"] is False
        ):
            raise ValidateException("输入审核和输出审核至少需要开启一项")
        if (
            review_config["inputs_config"]["enable"]
            and review_config["inputs_config"]["preset_response"].strip() == ""
        ):
            raise ValidateException("输入审核预设响应不能为空")
