<script setup lang="ts">
import CodeHighLight from '@/components/CodeHighLight.vue'
import {
  blockApiOutput,
  blockApiShell,
  streamApiOutput,
  streamApiShell,
} from '@/views/openapi/quick-start'
</script>

<template>
  <div class="pb-6">
    <div class="bg-white p-6 rounded-lg h-[calc(100vh-160px)] overflow-scroll scrollbar-w-none">
      <h2 class="text-base text-gray-700 font-bold mb-4">概览</h2>
      <p class="text-gray-700 mb-4">
        Flow LLMOps API 面向开发者开放平台能力，可以通过 API
        调用已发布的 Agent，并扩展模型、工作流、知识库和插件，让定制化 Agent 更精确、高效。
      </p>
      <h2 class="text-base text-gray-900 font-bold mb-4">准备工作</h2>
      <p class="text-gray-700 mb-4">
        在开始之前，需要先创建个人访问令牌，并在 Flow LLMOps 上完成 Agent 的创建与发布。
      </p>
      <h2 class="text-base text-gray-900 font-bold mb-4">基础使用</h2>
      <a-tabs type="text">
        <a-tab-pane key="block" title="非流式Chat">
          <p class="text-gray-700 mb-4">请求CURL</p>
          <code-high-light language="shell">{{ blockApiShell }}</code-high-light>
          <p class="text-gray-700 mb-4">返回结果示例</p>
          <code-high-light language="json">{{ blockApiOutput }}</code-high-light>
        </a-tab-pane>
        <a-tab-pane key="stream" title="流式Chat">
          <p class="text-gray-700 mb-4">请求CURL</p>
          <code-high-light language="shell">{{ streamApiShell }}</code-high-light>
          <p class="text-gray-700 mb-4">返回结果示例</p>
          <code-high-light language="json">{{ streamApiOutput }}</code-high-light>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<style scoped></style>
