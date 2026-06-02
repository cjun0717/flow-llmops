<script setup lang="ts">
import { computed } from 'vue'
import type { WorkflowNodeDebugResult } from '../../hooks/use-workflow-debug-results'

const props = defineProps<{
  result?: WorkflowNodeDebugResult | null
}>()

const isFailed = computed(() => props.result?.status === 'failed' || Boolean(props.result?.error))

const latencyText = computed(() => {
  const latency = Number(props.result?.latency)
  return Number.isFinite(latency) ? `${latency.toFixed(2)}s` : ''
})

const formatValue = (value: any) => {
  if (value === undefined || value === null || value === '') return '-'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const displayValue = computed(() => {
  if (!props.result) return ''
  if (isFailed.value) {
    return formatValue({
      error: props.result.error || '节点运行失败',
      outputs: props.result.outputs || {},
    })
  }
  return formatValue(props.result.outputs || {})
})
</script>

<template>
  <div
    v-if="props.result"
    class="nodrag nowheel flex flex-col gap-2 rounded-lg border p-3 text-xs"
    :class="
      isFailed
        ? 'border-red-200 bg-red-50 text-red-700'
        : 'border-emerald-200 bg-emerald-50 text-emerald-700'
    "
  >
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-1 font-semibold">
        <icon-exclamation-circle-fill v-if="isFailed" />
        <icon-check-circle-fill v-else />
        <span>{{ isFailed ? '运行错误' : '运行输出' }}</span>
      </div>
      <div v-if="latencyText" class="text-gray-500">{{ latencyText }}</div>
    </div>
    <pre
      class="max-h-[120px] overflow-y-auto whitespace-pre-wrap break-words rounded bg-white/80 p-2 leading-5 text-gray-700"
    >{{ displayValue }}</pre>
  </div>
</template>
