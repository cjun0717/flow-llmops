# ===== Flow LLMOps 后端镜像（api 与 celery 共用，靠启动命令区分角色）=====
FROM python:3.12-slim AS base

# 国内网络环境：ghcr.io 不可达，改用 pip + 清华镜像安装 uv；uv 下载依赖也走清华镜像
ENV UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple uv

WORKDIR /app

# 先拷贝依赖清单，充分利用构建缓存（--no-install-project 先只装依赖）
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# 再拷贝应用代码并安装项目本身
COPY app ./app
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    APP_RELOAD=false \
    DB_ECHO=false

EXPOSE 8001

# 默认以 API 角色启动；celery 角色在 compose 里用 command 覆盖
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]