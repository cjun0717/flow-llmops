# 🚀 Flow-LLMOps — AI 应用 / 智能体 / 工作流 一站式开发平台

<div align="center">

![Flow-LLMOps](assets/badges/flow-llmops.svg)
[![Python](assets/badges/python.svg)](https://python.org)
[![FastAPI](assets/badges/fastapi.svg)](https://fastapi.tiangolo.com)
[![Vue](assets/badges/vue.svg)](https://vuejs.org)
[![TypeScript](assets/badges/typescript.svg)](https://typescriptlang.org)
[![LangChain](assets/badges/langchain.svg)](https://python.langchain.com)
[![Docker](assets/badges/docker.svg)](https://docker.com)
[![License](assets/badges/license.svg)](LICENSE)

**FastAPI + Vue3 重构的开源 LLMOps 平台 · Agent 应用 · 拖拽式工作流 · 知识库 RAG · MCP 工具生态**

[快速开始](#-5-分钟快速开始docker-部署) · [技术架构](#-技术架构) · [模型管理](#-模型管理) · [工作流节点](#-工作流节点有哪些类型) · [工具生态](#-工具生态) · [常见问题](#-常见问题)

</div>

---

## Flow-LLMOps 是什么？

Flow-LLMOps 是一个**开箱即用的 LLMOps 平台**，参考 [imooc-llmops](resources/imooc-llmops/README.md)（Flask 版）的业务设计，使用 **FastAPI + Vue 3** 全栈重构。核心能力：Agent 应用调试与发布、拖拽式工作流编辑器、知识库 RAG、多模型管理、内置/API/MCP 工具生态、数据分析与全链路可观测。

**适合这些人群：**

- 想搭建 AI 客服 / 知识助手，但不想从零写代码的团队
- 学习 LLMOps 平台架构（FastAPI 异步后端 + Celery + LangGraph + Milvus RAG）的开发者
- 需要知识库检索增强（RAG）+ 工作流编排 + 可观测性的私有化部署场景
- 想体验从应用编排、发布、WebApp 分发到 OpenAPI 调用的完整闭环

**一句话总结**：5 分钟用 Docker 拉起一套能对话、能查知识库、能编排工作流、能观测 Token 成本的 AI 应用平台。

---

## 📋 目录

- [核心功能一览](#-核心功能一览)
- [5 分钟快速开始（Docker 部署）](#-5-分钟快速开始docker-部署)
- [本地开发](#-本地开发)
- [技术架构](#-技术架构)
- [模型管理](#-模型管理)
- [工作流节点有哪些类型？](#-工作流节点有哪些类型)
- [工具生态](#-工具生态)
- [项目结构](#-项目结构)
- [配置说明](#-怎么配置环境变量)
- [API 文档](#-api-文档)
- [开发命令速查](#-开发命令速查)
- [常见问题](#-常见问题)

---

## 🎯 核心功能一览

| 功能 | 说明 | 状态 |
|:-----|:-----|:-----|
| 🤖 **Agent 应用** | 预设提示词 + 模型参数 + 工具/知识库/工作流编排，内置调试会话（SSE 流式 + 运行流程展示） | ✅ |
| 🧠 **深度思考适配** | 思考型模型（DeepSeek-R1 / GLM / Qwen3 等）的 `reasoning_content` 实时推送为"运行流程"推理记录 | ✅ |
| 🎨 **拖拽式工作流** | VueFlow 画布，10 类节点自由编排，支持单节点调试 | ✅ |
| 📚 **知识库 RAG** | 文档上传 → 自动分块（jieba）→ 向量入库（Milvus）→ 检索增强生成，支持命中测试 | ✅ |
| 🔧 **多源工具** | 内置工具 / 自定义 API 工具 / OpenAPI 插件 / MCP Streamable HTTP 插件 | ✅ |
| 🧩 **模型管理** | 用户自添加 OpenAI 兼容模型（对话 + 向量），支持连通性探测、能力标记（工具调用 / 深度思考 / 视觉输入） | ✅ |
| 📤 **一键发布** | 应用发布历史 / 版本回退 / WebApp Token 分享链接 | ✅ |
| 🔑 **OpenAPI 开放** | API Key 管理 + 应用 OpenAPI 调用（REST，非流式） | ✅ |
| 📊 **数据分析** | Celery + ClickHouse 记录调用明细，ECharts 可视化 | ✅ |
| 🔍 **可观测性** | Langfuse 全链路追踪（替代 LangSmith），Token / 延迟 / 成本一目了然 | ✅ |
| 🎙️ **语音能力** | Whisper 语音转文本 / 文本转语音（未配置 `OPENAI_API_KEY` 时自动关闭） | ✅ |
| 🌐 **多渠道** | WebApp / 微信公众号接入 | ✅ |
| 🏪 **应用商店** | 内置应用模板 + 工具商店 | ✅ |

---

## 🚀 5 分钟快速开始（Docker 部署）

### 需要什么环境？

| 依赖 | 版本 |
|:-----|:-----|
| Docker + Docker Compose | 20+ |
| Git Bash（Windows 构建镜像用） | 任意 |

### 四步启动

```bash
# 1. 从模板生成本地环境变量（.env 含真实凭证，已被 .gitignore 排除，不会提交到仓库）
cd docker && cp .env.example .env

# 2. 构建前后端镜像（单 latest tag）
cd ../backend  && ./build.sh    # → flow-llmops-api:latest
cd ../frontend && ./build.sh    # → flow-llmops-web:latest

# 3. 启动全部服务（镜像预构建，compose 不含 build 段）
cd ../docker && docker compose up -d

# 4. 等待健康检查通过后访问
docker compose ps
```

### 启动后访问

| 服务 | 地址 | 说明 |
|:-----|:-----|:-----|
| **Web UI** | http://localhost:8080 | 主平台入口 |
| **API 服务** | http://localhost:8001/api/v1 | 后端接口 |
| **API 文档** | http://localhost:8001/docs | Swagger UI |
| **Langfuse** | http://localhost:3000 | LLM 链路追踪 |
| **MinIO 控制台** | http://localhost:9001 | 文件对象存储 |

### 默认账号

由 `docker/.env` 中的 `DEFAULT_ACCOUNT_*` 控制（服务启动时自动建表并幂等创建，**生产环境务必修改**）：

```text
用户名: chenjun
密码:   Chenjun@1024NB
```

### 首次登录后的推荐流程

1. **添加模型**：进入「个人空间 / 模型」→ 添加 OpenAI 兼容对话模型（填 Base URL + API Key → 一键探测模型列表），勾选能力（工具调用 / 深度思考 / 视觉输入）→ 设为默认。
2. **创建应用**：进入「个人空间 / 应用」→ 新建 Agent 应用 → 配置预设提示词、模型、工具。
3. **调试对话**：在应用详情页的「应用测试」里提问，实时查看流式回答、运行流程与 Token 统计。
4. **发布分享**：点击「发布」→ 复制 WebApp 链接，或到「OpenAPI」创建 API Key 用 REST 调用。

> 💡 思考型模型（DeepSeek-R1 / GLM / Qwen3 等）勾选「深度思考」后，思考过程会实时显示在调试界面的「运行流程」面板中。

---

## 💻 本地开发

### 后端（FastAPI + uv）

```bash
cd backend
uv sync                                            # 安装依赖
uv run uvicorn app.main:create_app --factory --reload --port 8001
```

后端启动时自动建表 + 种子默认账号，无需手动迁移。配置默认读取 `docker/.env`（首次使用先执行 `cp .env.example .env`，见 [配置说明](#-怎么配置环境变量)）。

### 前端（Vue 3 + Vite + yarn）

```bash
cd frontend
yarn install
yarn dev          # 开发服务器
```

生产构建时通过 `frontend/.env.production` 的 `VITE_API_PREFIX` 指定后端地址：

```env
VITE_API_PREFIX=http://localhost:8001/api/v1
```

---

## 🏗️ 技术架构

```
┌───────────────────────────────────────────────────────────────────┐
│                          Flow-LLMOps                              │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌────────────┐     ┌────────────┐     ┌──────────────────┐     │
│   │  flow-web  │     │  flow-api  │────▶│   flow-celery    │     │
│   │  (Vue 3)   │◀───▶│ (FastAPI)  │     │  (异步任务Worker) │     │
│   │   :8080    │ SSE │   :8001    │     │ 文档分块/数据分析 │     │
│   └────────────┘     └─────┬──────┘     └────────┬─────────┘     │
│                             │                     │               │
│         ┌───────────────────▼─────────────────────▼──────┐        │
│         │                     Redis                       │        │
│         │            (缓存 + Celery Broker)               │        │
│         └────────────────────┬────────────────────────────┘        │
│                              │                                    │
│   ┌──────────────┬───────────┼───────────┬───────────────┐        │
│   │  PostgreSQL  │   MinIO   │  Milvus   │  ClickHouse   │        │
│   │  (业务数据)  │ (对象存储) │ (向量检索) │ (调用分析)    │        │
│   └──────────────┴───────────┴───────────┴───────────────┘        │
│                                                                   │
│   可观测：Langfuse (worker + web) ← LangChain Callbacks           │
│   智能体：LangGraph 编排 · FunctionCallAgent / ReACTAgent          │
└───────────────────────────────────────────────────────────────────┘
```

### 后端技术栈

| 技术 | 用途 |
|:-----|:-----|
| Python 3.12 | 核心语言 |
| FastAPI | 异步 Web 框架（SSE 流式） |
| SQLAlchemy 2.0 (asyncpg) | 异步 ORM |
| Celery + Redis | 异步任务队列（文档处理 / 数据分析） |
| LangChain 1.x + LangGraph | 模型接入 / Agent 编排 |
| langchain-milvus | 向量检索 |
| MinIO | 文件对象存储 |
| Langfuse | LLM 全链路追踪 |

### 前端技术栈

| 技术 | 用途 |
|:-----|:-----|
| Vue 3 + TypeScript | UI 框架 |
| Arco Design Vue | 组件库 |
| Vite 5 | 构建工具 |
| VueFlow | 拖拽式工作流编辑器 |
| Tailwind CSS | 原子化样式 |
| Pinia + Vue Router | 状态管理 / 路由 |
| ECharts (vue-echarts) | 数据分析可视化 |

---

## 🧩 模型管理

平台**不预置任何模型**，全部通过「个人空间 / 模型」添加用户模型，凭证只存你自己的数据库：

| 配置项 | 说明 |
|:-------|:-----|
| Base URL | OpenAI 兼容地址（vLLM / DeepSeek / 智谱 / 硅基流动 / Ollama 等） |
| 模型服务名 | `/v1/chat/completions` 里的 `model` 字段 |
| 一键探测 | 调 `/v1/models` 自动列出可用模型，无需手填 |
| 能力标记 | `工具调用`（FunctionCallAgent）/ `深度思考`（思考过程实时展示）/ `视觉输入`（多模态图片上传） |
| 模型类型 | 对话模型（必填上下文长度） / 向量模型（必填维度，供知识库使用） |

**运行时行为**：

- 勾选「工具调用」→ 应用走 `FunctionCallAgent`（原生 tool calling 流式输出）；未勾选 → 走 `ReACTAgent`（文本协议推理）。
- 勾选「深度思考」→ 思考模型的 `reasoning_content` 流式推送为 `agent_thought` 事件，前端"运行流程"面板实时叠加展示。
- Token 统计优先使用服务端 `stream_options` 返回的真实用量，不可用时本地估算兜底。

---

## 🔀 工作流节点有哪些类型？

| 节点 | 功能 | 典型用途 |
|:-----|:-----|:---------|
| **Start / End** | 工作流入口 / 出口 | 定义输入变量与最终输出 |
| **LLM** | 调用大模型生成回复 | 问答、翻译、摘要 |
| **Code** | 执行 Python 代码片段 | 数据清洗、格式转换 |
| **HTTP Request** | 调用外部 REST API | 三方接口查询 |
| **Template Transform** | 模板变量渲染 | Prompt 拼装 |
| **Question Classifier** | 问题分类路由 | 意图识别分流 |
| **Dataset Retrieval** | 知识库检索 | RAG 文档召回 |
| **Tool** | 调用内置/API/MCP 工具 | 搜索、计算 |
| **Iteration** | 循环节点 | 批量处理数组 |

工作流可发布为独立应用，也可作为工具挂载到 Agent 应用的「工作流能力」中。

---

## 🔌 工具生态

| 来源 | 说明 |
|:-----|:-----|
| **内置工具** | 当前时间 / DuckDuckGo / Google / Wikipedia 搜索 / 高德天气 / DALL·E 文生图 / Markdown 转 PPT 等 |
| **API 工具** | 自定义 HTTP 接口封装 |
| **OpenAPI 插件** | 上传或填写 OpenAPI schema，按 operation 自动生成工具 |
| **MCP 插件** | 粘贴标准 `mcpServers` JSON，按 server 拆成插件卡片并同步 tools |

MCP 仅支持 **Streamable HTTP** 传输：

```json
{
  "mcpServers": {
    "demo-mcp": {
      "transport": "streamable-http",
      "url": "http://host.docker.internal:8765/mcp",
      "headers": {}
    }
  }
}
```

不支持本地 `stdio`、`command`、`args`、`sse`、`websocket`。MCP 工具运行时以 `mcp_<provider_uuid>_<tool_name>` 命名传给 LLM，便于与内置工具、OpenAPI 工具区分。

---

## 📁 项目结构

```
flow-llmops/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/routes/        # REST 路由（apps/datasets/workflows/tools...）
│   │   ├── core/               # agent / workflow / memory / language_model / tools
│   │   ├── models/             # SQLAlchemy ORM
│   │   ├── services/           # 业务逻辑
│   │   ├── tasks/              # Celery 任务
│   │   └── main.py             # create_app 工厂
│   ├── tests/                  # pytest（69 用例）
│   ├── Dockerfile              # python:3.12-slim + uv
│   └── build.sh
│
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── components/         # AgentThought / 消息组件等
│   │   ├── hooks/ use-app.ts / use-conversation.ts ...
│   │   ├── services/           # API 客户端（ssePost 流式）
│   │   └── views/              # pages / space / web-apps / openapi / store
│   ├── Dockerfile              # node:20 构建 + serve 运行
│   └── build.sh
│
├── docker/
│   ├── docker-compose.yaml     # 基础设施 + flow-api/flow-celery/flow-web
│   └── .env                    # 全部环境变量
│
├── resources/imooc-llmops/     # 原版 Flask 参考项目（只读）
└── README.md
```

---

## ⚙️ 怎么配置环境变量？

全部配置集中在 `docker/.env`，**该文件包含真实凭证、已被 `.gitignore` 排除，不会上传到 GitHub**；仓库只提交模板 `docker/.env.example`。首次部署先执行 `cp .env.example .env` 生成，后端 `app/config.py` 通过 pydantic-settings 读取；容器内由 compose `environment`/`env_file` 注入，同名变量以 `environment` 为准：

```env
# 基础设施（本地默认值，生产环境务必修改）
POSTGRES_USER=chenjun
POSTGRES_PASSWORD=chenjun1234
REDIS_AUTH=chenjun1234
MINIO_ROOT_USER=chenjun
MINIO_ROOT_PASSWORD=chenjun1234

# 默认登录账号（启动时幂等创建）
DEFAULT_ACCOUNT_NAME=chenjun
DEFAULT_ACCOUNT_PASSWORD=Chenjun@1024NB

# LangChain 追踪（对接 Langfuse，替代 LangSmith）
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=555
LANGFUSE_SECRET_KEY=666

# Whisper 语音转文本（不配置则语音功能自动关闭）
OPENAI_API_KEY=
```

> 模型凭证**不走环境变量**：对话/向量模型全部在前端「个人空间 / 模型」中添加，存于数据库。

---

## 📖 API 文档

| 文档 | 地址 |
|:-----|:-----|
| **Swagger UI** | http://localhost:8001/docs |
| **健康检查** | http://localhost:8001/ping |

### 核心 API 一览

| 方法 | 路径 | 说明 |
|:-----|:-----|:-----|
| POST | `/api/v1/auth/password-login` | 登录（JWT） |
| POST | `/api/v1/apps` | 创建应用 |
| POST | `/api/v1/apps/{app_id}/conversations` | 调试会话（SSE 流式） |
| POST | `/api/v1/apps/{app_id}/conversations/tasks/{task_id}/stop` | 停止调试会话 |
| POST | `/api/v1/apps/{app_id}/publish` | 发布应用 |
| POST | `/api/v1/datasets/{dataset_id}/documents` | 上传知识库文档 |
| GET | `/api/v1/analysis/{app_id}` | 应用数据分析 |
| POST | `/api/v1/openapi/chat` | API Key 调用（OpenAPI 开放接口） |
| POST | `/api/v1/web-apps/{token}/chat` | WebApp 分享链接对话 |

---

## 🔧 开发命令速查

```bash
# 后端测试（69 passed）
cd backend && uv run pytest -q

# 前端类型检查 / 构建
cd frontend && npx vue-tsc --build --force
cd frontend && yarn build

# 重建镜像并滚动更新
cd backend  && ./build.sh
cd frontend && ./build.sh
cd docker   && docker compose up -d flow-api flow-celery flow-web

# 查看后端日志（排查 Agent 执行异常）
docker logs -f flow-api --tail 200
```

---

## ❓ 常见问题

### Flow-LLMOps 是免费的吗？

是，MIT 协议开源，可自由用于学习和二次开发。服务器与模型 API 调用费用自理。

### 支持哪些大模型？

任何 OpenAI 兼容接口均可：vLLM / Ollama / DeepSeek / 智谱 GLM / 通义 Qwen / 硅基流动 / OpenAI 官方等。在「个人空间 / 模型」中添加，支持一键探测模型列表。

### 为什么调试对话会一直转圈？

早期版本在自定义模型名下调用 `get_num_tokens_from_messages` 抛 `NotImplementedError`，导致 `AGENT_END` 事件未发布、SSE 流不关闭。现已修复：token 统计改为"服务端用量优先 + 本地估算兜底"，且 LangGraph 线程任何异常都会发布 error 事件并关闭流。

### 知识库 RAG 是怎么工作的？

文档上传 → MinIO 存储 → Celery 异步分块（jieba）→ 向量模型生成 embedding → Milvus 入库；提问时按检索策略（top-k + 相似度阈值）召回片段注入上下文。支持命中测试调参。

### MCP 插件怎么接？

粘贴标准 `mcpServers` JSON（仅 Streamable HTTP），系统按 server 拆成插件卡片并同步工具列表。容器内访问本机服务用 `host.docker.internal`。

### 数据安全吗？可以自托管吗？

完全自托管。所有数据（用户、会话、知识库、文件）存储在你自己的 PostgreSQL / MinIO / Milvus 中，LLM 调用凭证仅存本地数据库，不经过任何第三方。

---

## 📄 许可证

MIT License，见 [LICENSE](LICENSE)。

---

<div align="center">

**如果这个项目对你有帮助，欢迎 Star / Fork / 提 Issue ⭐**

</div>

<!-- JSON-LD 结构化数据：AI 搜索引擎专用标记 -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Flow-LLMOps",
  "description": "FastAPI + Vue3 重构的开源 LLMOps 平台：Agent 应用、拖拽式工作流、知识库 RAG、MCP 工具生态、数据分析与 Langfuse 可观测。",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Linux, macOS, Windows",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "programmingLanguage": ["Python", "TypeScript"],
  "license": "https://opensource.org/licenses/MIT"
}
</script>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Flow-LLMOps 支持哪些大模型？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "任何 OpenAI 兼容接口均可：vLLM / Ollama / DeepSeek / 智谱 GLM / 通义 Qwen / 硅基流动 / OpenAI 官方等。在个人空间/模型中添加，支持一键探测模型列表。"
      }
    },
    {
      "@type": "Question",
      "name": "知识库 RAG 是怎么工作的？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "文档上传后由 Celery 异步分块（jieba），向量模型生成 embedding 存入 Milvus；提问时按检索策略召回相关片段注入大模型上下文，支持命中测试调参。"
      }
    },
    {
      "@type": "Question",
      "name": "可以自托管吗？数据安全吗？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "完全自托管，Docker Compose 一键部署。所有数据存储在你自己的 PostgreSQL / MinIO / Milvus 中，模型凭证仅存本地数据库。"
      }
    },
    {
      "@type": "Question",
      "name": "MCP 插件怎么接入？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "粘贴标准 mcpServers JSON（仅支持 Streamable HTTP 传输），系统按 server 拆成插件卡片并同步工具列表。"
      }
    }
  ]
}
</script>