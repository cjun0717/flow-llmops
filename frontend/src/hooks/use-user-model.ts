import { ref } from 'vue'
import { Form, Message, Modal } from '@arco-design/web-vue'
import {
  createUserModel,
  deleteUserModel,
  getUserModels,
  probeUserModel,
  setDefaultUserModel,
  updateUserModel,
} from '@/services/user-model'
import type { CreateUserModelRequest, UpdateUserModelRequest, UserModelItem, UserModelType } from '@/models/user-model'

const kToTokens = (k: number | null | undefined) => {
  if (k == null || Number.isNaN(Number(k))) return null
  return Math.round(Number(k) * 1000)
}

const tokensToK = (tokens: number | null | undefined) => {
  if (tokens == null || Number.isNaN(Number(tokens))) return null
  return Number(tokens) / 1000
}

export const formatContextWindow = (tokens: number | null | undefined) => {
  const k = tokensToK(tokens)
  if (k == null) return '-'
  return `${k}k`
}

export const useGetUserModels = () => {
  const loading = ref(false)
  const user_models = ref<UserModelItem[]>([])

  const loadUserModels = async (model_type?: UserModelType | '') => {
    try {
      loading.value = true
      const resp = await getUserModels(model_type)
      user_models.value = resp.data || []
    } finally {
      loading.value = false
    }
  }

  return { loading, user_models, loadUserModels }
}

export const useCreateOrUpdateUserModel = () => {
  const loading = ref(false)
  const defaultForm = {
    name: '',
    model_type: 'chat' as UserModelType,
    base_url: '',
    api_key: '',
    model_serve_name: '',
    context_window: 128 as number | null,
    max_length: null as number | null,
    dimension: null as number | null,
    features: [] as string[],
    is_default: false,
    verify: false,
  }
  const form = ref({ ...defaultForm })
  const formRef = ref<InstanceType<typeof Form>>()
  const showModal = ref(false)
  const editingId = ref('')

  const resetForm = () => {
    form.value = { ...defaultForm, features: [] }
    editingId.value = ''
  }

  const fillForm = (item: UserModelItem) => {
    editingId.value = item.id
    form.value = {
      name: item.name,
      model_type: item.model_type,
      base_url: item.base_url,
      api_key: '',
      model_serve_name: item.model_serve_name,
      context_window: tokensToK(item.context_window),
      max_length: item.max_length,
      dimension: item.dimension,
      features: [...(item.features || [])],
      is_default: item.is_default,
      verify: false,
    }
  }

  const saveUserModel = async () => {
    try {
      loading.value = true
      const context_window = form.value.model_type === 'chat' ? kToTokens(form.value.context_window) : null
      if (editingId.value) {
        const payload: UpdateUserModelRequest = {
          name: form.value.name,
          base_url: form.value.base_url,
          model_serve_name: form.value.model_serve_name,
          context_window,
          max_length: form.value.max_length,
          dimension: form.value.dimension,
          features: form.value.features,
          is_default: form.value.is_default,
          verify: form.value.verify,
        }
        if (form.value.api_key) payload.api_key = form.value.api_key
        const resp = await updateUserModel(editingId.value, payload)
        Message.success(resp.message)
      } else {
        const payload: CreateUserModelRequest = {
          name: form.value.name,
          model_type: form.value.model_type,
          base_url: form.value.base_url,
          api_key: form.value.api_key,
          model_serve_name: form.value.model_serve_name,
          context_window,
          max_length: form.value.max_length,
          dimension: form.value.dimension,
          features: form.value.features,
          is_default: form.value.is_default,
          verify: form.value.verify,
        }
        const resp = await createUserModel(payload)
        Message.success(resp.message)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, form, formRef, showModal, editingId, resetForm, fillForm, saveUserModel }
}

export const useDeleteUserModel = () => {
  const handleDelete = (model_id: string, callback?: () => void) => {
    Modal.warning({
      title: '要删除该模型吗?',
      content: '删除后，仍被应用或知识库引用的模型将无法删除。',
      hideCancel: false,
      onOk: async () => {
        try {
          const resp = await deleteUserModel(model_id)
          Message.success(resp.message)
        } finally {
          callback && callback()
        }
      },
    })
  }
  return { handleDelete }
}

export const useSetDefaultUserModel = () => {
  const handleSetDefault = async (model_id: string, callback?: () => void) => {
    const resp = await setDefaultUserModel(model_id)
    Message.success(resp.message)
    callback && callback()
  }
  return { handleSetDefault }
}

export const useProbeUserModel = () => {
  const loading = ref(false)
  const models = ref<{ id: string }[]>([])
  const handleProbe = async (base_url: string, api_key: string, model_type: UserModelType = 'chat') => {
    try {
      loading.value = true
      const resp = await probeUserModel({ base_url, api_key, model_type })
      models.value = resp.data?.models || []
      Message.success(`探测到 ${models.value.length} 个模型`)
      return models.value
    } finally {
      loading.value = false
    }
  }
  return { loading, models, handleProbe }
}
