<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useGetUserModels } from '@/hooks/use-user-model'
import { CHAT_PARAMETER_TEMPLATE, DEFAULT_CHAT_PARAMETERS } from '@/constants/chat-parameters'

const props = defineProps({
  model_config: {
    type: Object,
    default: () => {
      return {}
    },
    required: true,
  },
})
const emits = defineEmits(['update:model_config'])
const router = useRouter()
const form = ref<any>({})
const { loading: modelsLoading, user_models, loadUserModels } = useGetUserModels()
const modelOptions = computed(() =>
  user_models.value.map((item) => ({
    label: item.is_default ? `${item.name}（默认）` : item.name,
    value: item.id,
  })),
)
const selectedModel = computed(() =>
  user_models.value.find((item) => item.id === form.value.selectValue),
)

const changeModel = (value: string) => {
  const item = user_models.value.find((model) => model.id === value)
  form.value.parameters = { ...DEFAULT_CHAT_PARAMETERS, ...(item?.parameters || {}) }
}

const hideModelTrigger = () => {
  if (!form.value.selectValue) return
  emits('update:model_config', {
    user_model_id: form.value.selectValue,
    parameters: form.value.parameters,
  })
}

watch(
  () => props.model_config,
  (newValue) => {
    form.value.selectValue = newValue?.user_model_id || ''
    form.value.parameters = { ...DEFAULT_CHAT_PARAMETERS, ...(newValue?.parameters || {}) }
  },
  { immediate: true },
)

onMounted(() => {
  loadUserModels('chat')
})
</script>

<template>
  <a-trigger trigger="click" position="br" :popup-translate="[0, 12]" @hide="hideModelTrigger">
    <div class="flex items-center gap-1 cursor-pointer hover:bg-gray-100 px-1.5 py-1 rounded-lg">
      <a-avatar :size="16" shape="square">
        <icon-common />
      </a-avatar>
      <div class="text-gray-700 text-xs">{{ selectedModel?.name || '未选择模型' }}</div>
      <icon-down />
    </div>
    <template #content>
      <div class="bg-white px-6 py-5 shadow rounded-lg w-[460px]">
        <div class="text-gray-700 text-base font-semibold mb-3">模型设置</div>
        <div class="flex flex-col gap-2 mb-2">
          <div class="text-gray-700">模型</div>
          <a-select
            v-model:model-value="form.selectValue"
            :options="modelOptions"
            :loading="modelsLoading"
            size="small"
            class="rounded-lg mb-2"
            placeholder="请选择对话模型"
            allow-search
            @change="changeModel"
          />
          <div v-if="user_models.length === 0" class="text-xs text-gray-500 mb-2">
            还没有对话模型，请先到
            <a class="text-blue-600 cursor-pointer" @click="router.push('/space/models')">模型管理</a>
            添加。
          </div>
        </div>
        <div class="text-gray-700 mb-2">参数</div>
        <div
          v-for="parameter in CHAT_PARAMETER_TEMPLATE"
          :key="parameter.name"
          class="flex items-center gap-2 h-8 mb-4"
        >
          <div class="flex items-center gap-2 text-gray-500 w-[120px] flex-shrink-0">
            <div class="text-xs">{{ parameter.label }}</div>
            <a-tooltip :content="parameter.help">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <a-slider
            v-model:model-value="form.parameters[parameter.name]"
            :default-value="parameter.default"
            :min="parameter.min"
            :max="parameter.max"
            :step="parameter.type === 'float' ? 0.1 : 1"
            show-input
          />
        </div>
      </div>
    </template>
  </a-trigger>
</template>
