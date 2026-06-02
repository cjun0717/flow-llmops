import { ref } from 'vue'
import {
  createMcpToolProvider,
  deleteMcpToolProvider,
  getMcpTool,
  getMcpToolProvider,
  getMcpToolProvidersWithPage,
  updateMcpToolProvider,
  validateMcpSchema,
} from '@/services/mcp-tool'
import { Message, Modal } from '@arco-design/web-vue'
import type {
  CreateMcpToolProviderRequest,
  UpdateMcpToolProviderRequest,
} from '@/models/mcp-tool'

export const useGetMcpToolProvider = () => {
  const loading = ref(false)
  const mcp_tool_provider = ref<Record<string, any>>({})

  const loadMcpToolProvider = async (provider_id: string) => {
    try {
      loading.value = true
      const resp = await getMcpToolProvider(provider_id)
      mcp_tool_provider.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, mcp_tool_provider, loadMcpToolProvider }
}

export const useGetMcpTool = () => {
  const loading = ref(false)
  const mcp_tool = ref<Record<string, any>>({})

  const loadMcpTool = async (provider_id: string, tool_name: string) => {
    try {
      loading.value = true
      const resp = await getMcpTool(provider_id, tool_name)
      mcp_tool.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, mcp_tool, loadMcpTool }
}

export const useGetMcpToolProvidersWithPage = () => {
  const loading = ref(false)
  const mcp_tool_providers = ref<Record<string, any>>([])
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref(defaultPaginator)

  const loadMcpToolProviders = async (init: boolean = false, search_word: string = '') => {
    if (init) {
      paginator.value = defaultPaginator
      Object.assign(paginator, { ...defaultPaginator })
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    try {
      loading.value = true
      const resp = await getMcpToolProvidersWithPage(
        paginator.value.current_page,
        paginator.value.page_size,
        search_word,
      )
      const data = resp.data
      paginator.value = data.paginator
      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }
      if (init) {
        mcp_tool_providers.value = data.list
      } else {
        mcp_tool_providers.value.push(...data.list)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, mcp_tool_providers, paginator, loadMcpToolProviders }
}

export const useDeleteMcpToolProvider = () => {
  const handleDelete = (provider_id: string, success_callback?: () => void) => {
    Modal.warning({
      title: '删除这个MCP服务器?',
      content: '删除后，AI应用和工作流将无法再访问该MCP服务器的工具',
      hideCancel: false,
      onOk: async () => {
        try {
          const resp = await deleteMcpToolProvider(provider_id)
          Message.success(resp.message)
        } finally {
          success_callback && success_callback()
        }
      },
    })
  }

  return { handleDelete }
}

export const useUpdateMcpToolProvider = () => {
  const loading = ref(false)

  const handleUpdateMcpToolProvider = async (
    provider_id: string,
    req: UpdateMcpToolProviderRequest,
  ) => {
    try {
      loading.value = true
      const resp = await updateMcpToolProvider(provider_id, req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateMcpToolProvider }
}

export const useCreateMcpToolProvider = () => {
  const loading = ref(false)

  const handleCreateMcpToolProvider = async (req: CreateMcpToolProviderRequest) => {
    try {
      loading.value = true
      const resp = await createMcpToolProvider(req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleCreateMcpToolProvider }
}

export const useValidateMcpSchema = () => {
  const loading = ref(false)
  const preview = ref<Record<string, any>[]>([])

  const handleValidateMcpSchema = async (mcp_schema: string) => {
    try {
      loading.value = true
      const resp = await validateMcpSchema(mcp_schema)
      preview.value = resp.data
      Message.success('MCP服务器校验成功')
      return resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, preview, handleValidateMcpSchema }
}
