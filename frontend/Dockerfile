# ===== Flow LLMOps 前端镜像（不使用 nginx，构建产物由 serve 提供静态服务）=====

# 一阶段：构建 Vue 静态产物
FROM node:20-alpine AS builder

WORKDIR /app/web

# 先拷贝依赖清单，充分利用构建缓存
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

# 拷贝项目代码并构建
# VITE_API_PREFIX 取 .env.production（默认 http://localhost:8001/api/v1），
# 浏览器直连后端，跨域由后端 CORS 处理
COPY . .
RUN yarn build

# 二阶段：用 serve 提供静态文件（-s 开启 SPA 回退到 index.html）
FROM node:20-alpine

WORKDIR /app
RUN yarn global add serve@14

COPY --from=builder /app/web/dist ./dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]
