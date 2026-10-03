<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { ValidatedError } from '@arco-design/web-vue'
import {
  formatContextWindow,
  useCreateOrUpdateUserModel,
  useDeleteUserModel,
  useGetUserModels,
  useProbeUserModel,
  useSetDefaultUserModel,
} from '@/hooks/use-user-model'
import type { UserModelItem, UserModelType } from '@/models/user-model'

const props = defineProps({
  createType: { type: String, required: true },
})
const emits = defineEmits(['update:create-type'])
const typeFilter = ref<'' | UserModelType>('')
const { loading, user_models, loadUserModels } = useGetUserModels()
const {
  loading: submitLoading,
  form,
  formRef,
  showModal,
  editingId,
  resetForm,
  fillForm,
  saveUserModel,
} = useCreateOrUpdateUserModel()
const { handleDelete } = useDeleteUserModel()
const { handleSetDefault } = useSetDefaultUserModel()
const { loading: probeLoading, models: probedModels, handleProbe } = useProbeUserModel()

const isChat = computed(() => form.value.model_type === 'chat')
const featureOptions = [
  { label: '工具调用', value: 'tool_call' },
  { label: '深度思考', value: 'agent_thought' },
  { label: '视觉输入', value: 'image_input' },
]
const serveNameOptions = computed(() =>
  probedModels.value.map((item) => ({ label: item.id, value: item.id })),
)

const typeLabel = (type: string) => (type === 'embedding' ? '向量' : '对话')

const openCreate = () => {
  resetForm()
  showModal.value = true
}

const openEdit = (item: UserModelItem) => {
  fillForm(item)
  showModal.value = true
}

const handleCancel = () => {
  showModal.value = false
  resetForm()
  emits('update:create-type', '')
}

const handleSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  if (errors) return
  await saveUserModel()
  handleCancel()
  await loadUserModels(typeFilter.value)
}

const probe = async () => {
  if (!form.value.base_url) return
  await handleProbe(form.value.base_url, form.value.api_key, form.value.model_type)
}

watch(
  () => props.createType,
  (value) => {
    if (value === 'model') openCreate()
  },
)

watch(typeFilter, () => loadUserModels(typeFilter.value))

onMounted(() => {
  loadUserModels(typeFilter.value)
})
</script>

<template>
  <a-spin :loading="loading" class="block h-full w-full scrollbar-w-none overflow-scroll">
    <div class="flex items-center gap-2 mb-4">
      <a-radio-group v-model="typeFilter" type="button" size="small">
        <a-radio value="">全部</a-radio>
        <a-radio value="chat">对话</a-radio>
        <a-radio value="embedding">向量</a-radio>
      </a-radio-group>
    </div>
    <a-row :gutter="[20, 20]">
      <a-col v-for="item in user_models" :key="item.id" :span="8">
        <a-card hoverable class="rounded-lg">
          <div class="flex items-start justify-between mb-3">
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <div class="text-base text-gray-900 font-bold line-clamp-1">{{ item.name }}</div>
                <a-tag v-if="item.is_default" color="arcoblue" size="small">默认</a-tag>
              </div>
              <div class="text-xs text-gray-500 mt-1">
                {{ typeLabel(item.model_type) }} · {{ item.model_serve_name }}
              </div>
            </div>
            <a-dropdown position="br">
              <a-button type="text" size="small" class="rounded-lg !text-gray-700">
                <template #icon><icon-more /></template>
              </a-button>
              <template #content>
                <a-doption @click="openEdit(item)">编辑</a-doption>
                <a-doption v-if="!item.is_default" @click="handleSetDefault(item.id, () => loadUserModels(typeFilter))">
                  设为默认
                </a-doption>
                <a-doption class="!text-red-500" @click="handleDelete(item.id, () => loadUserModels(typeFilter))">
                  删除
                </a-doption>
              </template>
            </a-dropdown>
          </div>
          <div class="text-xs text-gray-400 break-all">{{ item.base_url }}</div>
          <div v-if="item.model_type === 'embedding'" class="text-xs text-gray-500 mt-2">
            维度 {{ item.dimension || '-' }}
          </div>
          <div v-else class="text-xs text-gray-500 mt-2">
            上下文 {{ formatContextWindow(item.context_window) }}
          </div>
        </a-card>
      </a-col>
      <a-col v-if="user_models.length === 0" :span="24">
        <a-empty description="还没有模型，点击右上角添加对话或向量模型" class="h-[360px] flex flex-col items-center justify-center" />
      </a-col>
    </a-row>

    <a-modal :width="560" :visible="showModal" hide-title :footer="false" modal-class="rounded-xl" @cancel="handleCancel">
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">{{ editingId ? '编辑模型' : '添加模型' }}</div>
        <a-button type="text" class="!text-gray-700" size="small" @click="handleCancel">
          <template #icon><icon-close /></template>
        </a-button>
      </div>
      <div class="pt-6">
        <a-form ref="formRef" :model="form" layout="vertical" @submit="handleSubmit">
          <a-form-item field="name" label="显示名称" :rules="[{ required: true, message: '请输入名称' }]">
            <a-input v-model="form.name" placeholder="例如 DeepSeek Chat" :max-length="100" />
          </a-form-item>
          <a-form-item field="model_type" label="类型">
            <a-radio-group v-model="form.model_type" :disabled="Boolean(editingId)">
              <a-radio value="chat">对话</a-radio>
              <a-radio value="embedding">向量</a-radio>
            </a-radio-group>
          </a-form-item>
          <a-form-item field="base_url" label="Base URL" :rules="[{ required: true, message: '请输入 Base URL' }]">
            <a-input v-model="form.base_url" placeholder="https://api.example.com/v1" />
          </a-form-item>
          <a-form-item field="api_key" :label="editingId ? 'API Key（留空表示不修改）' : 'API Key'" :rules="editingId ? [] : [{ required: true, message: '请输入 API Key' }]">
            <a-input-password v-model="form.api_key" placeholder="sk-..." />
          </a-form-item>
          <a-form-item field="model_serve_name" label="模型服务名" :rules="[{ required: true, message: '请输入或探测模型服务名' }]">
            <div class="flex w-full gap-2">
              <a-select
                v-if="serveNameOptions.length"
                v-model="form.model_serve_name"
                allow-create
                allow-search
                placeholder="选择或输入模型服务名"
                :options="serveNameOptions"
                class="flex-1"
              />
              <a-input v-else v-model="form.model_serve_name" class="flex-1" placeholder="例如 deepseek-chat" />
              <a-button :loading="probeLoading" @click="probe">探测</a-button>
            </div>
          </a-form-item>
          <a-form-item v-if="isChat" field="context_window" label="上下文长度" :rules="[{ required: true, message: '请填写上下文长度' }]">
            <a-input-number v-model="form.context_window" :min="1" :precision="0" class="w-full" placeholder="128">
              <template #suffix>k</template>
            </a-input-number>
          </a-form-item>
          <a-form-item v-else field="dimension" label="向量维度" :rules="[{ required: true, message: '请填写向量维度' }]">
            <a-input-number v-model="form.dimension" :min="1" :max="8192" class="w-full" placeholder="例如 1536" />
          </a-form-item>
          <a-form-item v-if="isChat" field="features" label="能力">
            <a-checkbox-group v-model="form.features" :options="featureOptions" />
          </a-form-item>
          <a-form-item field="is_default">
            <a-checkbox v-model="form.is_default">设为该类型默认模型</a-checkbox>
          </a-form-item>
          <a-form-item field="verify">
            <a-checkbox v-model="form.verify">保存前探测连通性</a-checkbox>
          </a-form-item>
          <div class="flex items-center justify-end">
            <a-space :size="16">
              <a-button class="rounded-lg" @click="handleCancel">取消</a-button>
              <a-button :loading="submitLoading" type="primary" html-type="submit" class="rounded-lg">保存</a-button>
            </a-space>
          </div>
        </a-form>
      </div>
    </a-modal>
  </a-spin>
</template>
