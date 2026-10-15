# Flow-LLMOps 后端服务

> 项目总览、快速开始（Docker）、架构图与 FAQ 见仓库根目录 [README](../README.md)。
> 本文档面向需要阅读 / 修改后端代码的开发者。

FastAPI + LangGraph 构建的一站式大模型应用开发平台后端，提供应用编排、Agent 调试、
工作流引擎、知识库 RAG、模型管理等完整 API。

## 技术栈

| 类别 | 选型 |
| --- | --- |
| 语言 / 包管理 | Python 3.12 + uv（依赖锁定于 `uv.lock`） |
| Web 框架 | FastAPI + uvicorn |
| 数据库 | PostgreSQL（SQLAlchemy 2.x async + asyncpg） |
| 缓存 / 队列 | Redis（同步 + asyncio 双客户端） |
| 异步任务 | Celery（`app.tasks.celery_app`） |
| LLM 编排 | LangChain 1.x 基础四件套：`langchain` / `langchain-core` / `langgraph` / `langchain-openai` |
| 向量数据库 | Milvus（`pymilvus` 直连，按维度分 collection） |
| 对象存储 | MinIO |
| 可观测性 | Langfuse（LangChain / LangGraph 回调追踪） |

## 目录结构

```
backend/
├── pyproject.toml        # 依赖声明（uv）
├── uv.lock               # 精确锁定版本（含 hash，请提交）
├── app/
│   ├── main.py           # FastAPI 应用入口（factory: create_app）
│   ├── config.py         # pydantic-settings 配置（.env 驱动）
│   ├── api/              # 路由层（/api/v1）
│   ├── schemas/          # 请求 / 响应模型
│   ├── services/         # 业务服务层
│   ├── models/           # SQLAlchemy ORM 模型
│   ├── entities/         # 内部领域实体 / 枚举
│   ├── core/             # 引擎核心：agent、workflow、language_model、
│   │                     #   tools、file_extractor、memory、observalibity
│   ├── tasks/            # Celery 异步任务
│   ├── lib/              # 通用工具（dalle 客户端、helper 等）
│   ├── middlewares/      # 中间件
│   ├── exceptions/       # 异常与全局异常处理
│   └── utils/            # 杂项工具
└── tests/                # pytest 用例（asyncio_mode = auto）
```

## 本地开发

### 1. 准备基础设施

后端依赖 Redis / PostgreSQL / Milvus / MinIO 等服务，最简单的方式是启动仓库根目录的
Docker Compose（只跑基础设施容器即可）：

```bash
cd docker && cp .env.example .env
docker compose up -d redis postgres milvus minio
```

### 2. 安装依赖

```bash
cd backend
uv sync --group test    # 按锁文件精确安装（含测试依赖）
```

### 3. 环境变量

后端配置由 `app/config.py` 统一从仓库根目录的 **`docker/.env`** 读取
（基础设施与后端共用一份配置），第 1 步中 `cp .env.example .env` 已生成。
本地开发时确认其中连接地址指向 `localhost`，启动相关服务即可。

### 4. 启动服务

```bash
# API 服务（默认 8001，reload 由 APP_RELOAD 控制）
uv run python -m app.main

# Celery Worker（另一个终端；应用编排等异步任务依赖它）
uv run celery -A app.tasks.celery_app worker --loglevel=info
```

## 运行测试

```bash
uv run pytest -q
```

约定：所有新增能力必须有对应用例；涉及外部服务的用例在无服务时自动 skip。
当前基线：**69 passed, 72 skipped**。

## 依赖管理约定

- 依赖只写在 `pyproject.toml`，版本使用**窄区间约束**（如 `langchain>=1.4.6,<2`），
  精确版本由 `uv.lock` 锁定（含 hash）——`uv.lock` 必须提交入库
- 修改依赖后：`uv lock` 重新锁定 → `uv sync --group test` 同步环境 → 跑测试回归
- 校验锁文件与声明是否一致：`uv lock --check`
- **LangChain 生态只保留基础四件套**（`langchain` / `langchain-core` / `langgraph` /
  `langchain-openai`），新增任何外部能力一律安装独立的 `langchain-xxx` 分包，
  不再引入 `langchain-community` / `langchain-classic`（前者已停止维护，后者仅为过渡兼容包）
- 非 LangChain 能力直接使用独立库（本项目实际使用：`pymilvus`、`unstructured`、
  `duckduckgo-search`、`wikipedia`、`openai` SDK 等）
- 模型接入统一走 OpenAI 兼容协议（`app/core/language_model/openai_compatible.py`），
  凭证来自前端「模型管理」，不使用厂商专用 SDK

## 已知注意事项

- 文档解析基于 `unstructured`：PPT / Excel / PDF / docx 等格式需要在环境中具备
  对应的运行时依赖（`openpyxl`、`python-docx`、`pdfminer.six` 等），纯文本（txt）不受影响
- `unstructured` 首次解析文本类文件会尝试联网下载 spaCy 英文模型（`en_core_web_sm`），
  内网环境建议预先安装进镜像
- tiktoken 词表首次使用需联网，构建镜像时建议预置缓存
  （`TIKTOKEN_CACHE_DIR` 指向 `%TEMP%\data-gym-cache`）

## 部署

生产部署统一使用 Docker Compose（`docker/docker-compose.yaml` 中的 `flow-api` 与
`flow-celery`，共用同一个后端镜像），完整流程见根 README 的「快速开始」。