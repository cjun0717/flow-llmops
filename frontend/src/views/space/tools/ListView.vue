<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  useCreateApiToolProvider,
  useDeleteApiToolProvider,
  useGetApiToolProvider,
  useGetApiToolProvidersWithPage,
  useUpdateApiToolProvider,
  useValidateOpenAPISchema,
} from '@/hooks/use-tool'
import {
  useCreateMcpToolProvider,
  useDeleteMcpToolProvider,
  useGetMcpToolProvider,
  useGetMcpToolProvidersWithPage,
  useUpdateMcpToolProvider,
  useValidateMcpSchema,
} from '@/hooks/use-mcp-tool'
import { useUploadImage } from '@/hooks/use-upload-file'
import { type CreateApiToolProviderRequest } from '@/models/api-tool'
import { type CreateMcpToolProviderRequest } from '@/models/mcp-tool'
import moment from 'moment/moment'
import { typeMap } from '@/config'
import { type FileItem, Form, type ValidatedError } from '@arco-design/web-vue'

const route = useRoute()
const props = defineProps({
  createType: { type: String, required: true },
})
const emits = defineEmits(['update:create-type'])

const openApiForm = ref<{
  fileList: FileItem[]
  icon: string
  name: string
  openapi_schema: string
  headers: Record<string, any>[]
}>({
  fileList: [],
  icon: '',
  name: '',
  openapi_schema: '',
  headers: [],
})
const mcpForm = ref<{ mcp_schema: string }>({
  mcp_schema: '',
})

const { handleUploadImage } = useUploadImage()
const { loading: getApiToolProviderLoading, api_tool_provider, loadApiToolProvider } =
  useGetApiToolProvider()
const {
  loading: getApiToolProvidersLoading,
  paginator: apiPaginator,
  api_tool_providers,
  loadApiToolProviders,
} = useGetApiToolProvidersWithPage()
const { handleDelete: handleDeleteApiToolProvider } = useDeleteApiToolProvider()
const { loading: updateApiToolProviderLoading, handleUpdateApiToolProvider } =
  useUpdateApiToolProvider()
const { loading: createApiToolProviderLoading, handleCreateApiToolProvider } =
  useCreateApiToolProvider()
const { handleValidateOpenAPISchema } = useValidateOpenAPISchema()

const { loading: getMcpToolProviderLoading, mcp_tool_provider, loadMcpToolProvider } =
  useGetMcpToolProvider()
const {
  loading: getMcpToolProvidersLoading,
  paginator: mcpPaginator,
  mcp_tool_providers,
  loadMcpToolProviders,
} = useGetMcpToolProvidersWithPage()
const { handleDelete: handleDeleteMcpToolProvider } = useDeleteMcpToolProvider()
const { loading: updateMcpToolProviderLoading, handleUpdateMcpToolProvider } =
  useUpdateMcpToolProvider()
const { loading: createMcpToolProviderLoading, handleCreateMcpToolProvider } =
  useCreateMcpToolProvider()
const {
  loading: validateMcpSchemaLoading,
  preview: mcpRemotePreview,
  handleValidateMcpSchema,
} = useValidateMcpSchema()

const openApiFormRef = ref<InstanceType<typeof Form>>()
const mcpFormRef = ref<InstanceType<typeof Form>>()
const showIdx = ref<number>(-1)
const showOpenApiUpdateModal = ref<boolean>(false)
const showMcpUpdateModal = ref<boolean>(false)

const pluginProviders = computed(() => {
  const apiProviders = api_tool_providers.value.map((item: any) => ({
    ...item,
    plugin_type: 'api_tool',
    plugin_label: 'OpenAPI',
  }))
  const mcpProviders = mcp_tool_providers.value.map((item: any) => ({
    ...item,
    plugin_type: 'mcp_tool',
    plugin_label: 'MCP',
    icon: '',
  }))
  return [...apiProviders, ...mcpProviders]
})
const activeProvider = computed(() => {
  if (showIdx.value === -1) return {}
  return pluginProviders.value[showIdx.value] ?? {}
})
const loading = computed(() => getApiToolProvidersLoading.value || getMcpToolProvidersLoading.value)
const hasMore = computed(() => {
  const apiHasMore =
    apiPaginator.value.total_page >= 2 &&
    apiPaginator.value.current_page <= apiPaginator.value.total_page
  const mcpHasMore =
    mcpPaginator.value.total_page >= 2 &&
    mcpPaginator.value.current_page <= mcpPaginator.value.total_page
  return apiHasMore || mcpHasMore
})
const apiToolsPreview = computed(() => {
  try {
    const availableTools = []
    const openapiSchema = JSON.parse(openApiForm.value.openapi_schema)
    if ('paths' in openapiSchema) {
      for (const path in openapiSchema.paths) {
        for (const method in openapiSchema.paths[path]) {
          if (['get', 'post'].includes(method)) {
            const tool = openapiSchema.paths[path][method]
            if ('operationId' in tool && 'description' in tool) {
              availableTools.push({
                name: tool.operationId,
                description: tool.description,
                method,
                path,
              })
            }
          }
        }
      }
    }
    return availableTools
  } catch (e) {
    return []
  }
})
const mcpServersPreview = computed(() => {
  if (mcpRemotePreview.value.length > 0) return mcpRemotePreview.value
  try {
    const mcpSchema = JSON.parse(mcpForm.value.mcp_schema)
    const servers = mcpSchema?.mcpServers ?? {}
    return Object.entries(servers)
      .filter(([, config]: any) => config?.disabled !== true)
      .map(([name, config]: any) => ({
        name,
        description: config?.description ?? '',
        config: {
          transport: config?.transport ?? 'http',
          url: config?.url ?? '',
          headers: config?.headers ?? {},
        },
        tools: [],
      }))
  } catch (e) {
    return []
  }
})

const loadProviders = async (init = true) => {
  const searchWord = String(route.query?.search_word ?? '')
  await Promise.all([
    loadApiToolProviders(init, searchWord),
    loadMcpToolProviders(init, searchWord),
  ])
}

const handleScroll = (event: UIEvent) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (loading.value) return
    const searchWord = String(route.query?.search_word ?? '')
    loadApiToolProviders(false, searchWord)
    loadMcpToolProviders(false, searchWord)
  }
}

const resetOpenApiForm = () => {
  openApiFormRef.value?.resetFields()
  openApiForm.value = {
    fileList: [],
    icon: '',
    name: '',
    openapi_schema: '',
    headers: [],
  }
}

const resetMcpForm = () => {
  mcpFormRef.value?.resetFields()
  mcpForm.value = { mcp_schema: '' }
  mcpRemotePreview.value = []
}

const handleUpdate = async () => {
  const provider = activeProvider.value
  if (!provider?.id) return

  if (provider.plugin_type === 'api_tool') {
    await loadApiToolProvider(provider.id)
    resetOpenApiForm()
    openApiForm.value.fileList = [{ uid: '1', name: '插件图标', url: api_tool_provider.value.icon }]
    openApiForm.value.icon = api_tool_provider.value.icon
    openApiForm.value.name = api_tool_provider.value.name
    openApiForm.value.openapi_schema = api_tool_provider.value.openapi_schema
    openApiForm.value.headers = api_tool_provider.value.headers
    showOpenApiUpdateModal.value = true
  } else {
    await loadMcpToolProvider(provider.id)
    resetMcpForm()
    mcpForm.value.mcp_schema = mcp_tool_provider.value.mcp_schema
    mcpRemotePreview.value = [
      {
        name: mcp_tool_provider.value.name,
        description: mcp_tool_provider.value.description,
        config: mcp_tool_provider.value.config,
        tools: mcp_tool_provider.value.tools,
      },
    ]
    showMcpUpdateModal.value = true
  }
}

const handleDelete = () => {
  const provider = activeProvider.value
  if (!provider?.id) return

  const successCallback = async () => {
    handleCancel()
    showIdx.value = -1
    await loadProviders(true)
  }

  if (provider.plugin_type === 'api_tool') {
    handleDeleteApiToolProvider(provider.id, successCallback)
  } else {
    handleDeleteMcpToolProvider(provider.id, successCallback)
  }
}

const handleSubmitOpenApi = async ({
  values,
  errors,
}: {
  values: Record<string, any>
  errors: Record<string, ValidatedError> | undefined
}) => {
  if (errors) return
  if (props.createType === 'tool') {
    await handleCreateApiToolProvider(values as CreateApiToolProviderRequest)
  } else if (showOpenApiUpdateModal.value) {
    await handleUpdateApiToolProvider(activeProvider.value.id, values as CreateApiToolProviderRequest)
  }
  handleCancel()
  showIdx.value = -1
  await loadProviders(true)
}

const handleSubmitMcp = async ({
  values,
  errors,
}: {
  values: Record<string, any>
  errors: Record<string, ValidatedError> | undefined
}) => {
  if (errors) return
  if (props.createType === 'mcp_tool') {
    await handleCreateMcpToolProvider(values as CreateMcpToolProviderRequest)
  } else if (showMcpUpdateModal.value) {
    await handleUpdateMcpToolProvider(activeProvider.value.id, values as CreateMcpToolProviderRequest)
  }
  handleCancel()
  showIdx.value = -1
  await loadProviders(true)
}

const handleCancel = () => {
  resetOpenApiForm()
  resetMcpForm()
  emits('update:create-type', '')
  showOpenApiUpdateModal.value = false
  showMcpUpdateModal.value = false
}

const getProviderIconText = (provider: Record<string, any>) => {
  return provider.plugin_type === 'mcp_tool' ? 'MCP' : ''
}

onMounted(() => loadProviders(true))

watch(
  () => route.query?.search_word,
  () => {
    loadProviders(true)
  },
)

watch(
  () => route.query?.create_type,
  (newValue) => {
    if (newValue === 'tool' || newValue === 'mcp_tool') emits('update:create-type', String(newValue))
  },
  { immediate: true },
)
</script>

<template>
  <a-spin
    :loading="loading"
    class="block h-full w-full scrollbar-w-none overflow-scroll"
    @scroll="handleScroll"
  >
    <a-row :gutter="[20, 20]" class="flex-1">
      <a-col v-for="(provider, idx) in pluginProviders" :key="`${provider.plugin_type}-${provider.id}`" :span="6">
        <a-card hoverable class="cursor-pointer rounded-lg" @click="showIdx = Number(idx)">
          <div class="flex items-center gap-3 mb-3">
            <a-avatar
              v-if="provider.plugin_type === 'api_tool'"
              :size="40"
              shape="square"
              class="rounded-lg flex-shrink-0"
              :image-url="provider.icon"
            />
            <a-avatar v-else :size="40" shape="square" class="bg-gray-900 rounded-lg text-xs flex-shrink-0">
              {{ getProviderIconText(provider) }}
            </a-avatar>
            <div class="flex flex-col min-w-0 flex-1">
              <div class="flex items-center gap-2 min-w-0">
                <div class="text-base text-gray-900 font-bold line-clamp-1 break-all">
                  {{ provider.name }}
                </div>
                <a-tag size="small" :color="provider.plugin_type === 'mcp_tool' ? 'arcoblue' : 'green'">
                  {{ provider.plugin_label }}
                </a-tag>
              </div>
              <div class="text-xs text-gray-500 line-clamp-1">
                提供商 {{ provider.name }} · {{ provider.tools.length }} 插件
              </div>
            </div>
          </div>
          <div class="leading-[18px] text-gray-500 h-[72px] line-clamp-4 mb-2">
            {{ provider.description }}
          </div>
          <div class="flex items-center gap-1.5">
            <a-avatar :size="18" class="bg-blue-700">
              <icon-user />
            </a-avatar>
            <div class="text-xs text-gray-400">
              慕小课 · 编辑时间
              {{ moment((provider.updated_at || provider.created_at) * 1000).format('MM-DD HH:mm') }}
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col v-if="pluginProviders.length === 0" :span="24">
        <a-empty
          description="没有可用的插件"
          class="h-[400px] flex flex-col items-center justify-center"
        />
      </a-col>
    </a-row>

    <a-row v-if="hasMore">
      <a-col :span="24" align="center">
        <a-space class="my-4">
          <a-spin />
          <div class="text-gray-400">加载中</div>
        </a-space>
      </a-col>
    </a-row>

    <a-drawer
      :visible="showIdx != -1"
      :width="350"
      :footer="false"
      title="工具详情"
      :drawer-style="{ background: '#F9FAFB' }"
      @cancel="showIdx = -1"
    >
      <div v-if="showIdx != -1" class="">
        <div class="flex items-center gap-3 mb-3">
          <a-avatar
            v-if="activeProvider.plugin_type === 'api_tool'"
            :size="40"
            shape="square"
            class="rounded-lg flex-shrink-0"
            :image-url="activeProvider.icon"
          />
          <a-avatar v-else :size="40" shape="square" class="bg-gray-900 rounded-lg text-xs flex-shrink-0">
            MCP
          </a-avatar>
          <div class="flex flex-col min-w-0 flex-1">
            <div class="flex items-center gap-2 min-w-0">
              <div class="text-base text-gray-900 font-bold line-clamp-1 break-all">
                {{ activeProvider.name }}
              </div>
              <a-tag size="small" :color="activeProvider.plugin_type === 'mcp_tool' ? 'arcoblue' : 'green'">
                {{ activeProvider.plugin_label }}
              </a-tag>
            </div>
            <div class="text-xs text-gray-500 line-clamp-1">
              提供商 {{ activeProvider.name }} · {{ activeProvider.tools.length }} 插件
            </div>
          </div>
        </div>
        <div class="leading-[18px] text-gray-500 mb-4">
          {{ activeProvider.description }}
        </div>
        <div v-if="activeProvider.plugin_type === 'mcp_tool'" class="text-xs text-gray-500 mb-4 break-all">
          {{ activeProvider.url }}
        </div>
        <a-button
          :loading="getApiToolProviderLoading || getMcpToolProviderLoading"
          type="dashed"
          long
          class="mb-2 rounded-lg"
          @click="handleUpdate"
        >
          <template #icon>
            <icon-settings />
          </template>
          编辑工具
        </a-button>
        <hr class="my-4" />
        <div class="flex flex-col gap-2">
          <div class="text-xs text-gray-500">包含 {{ activeProvider.tools.length }} 个工具</div>
          <a-card
            v-for="tool in activeProvider.tools"
            :key="tool.name"
            class="cursor-pointer flex flex-col rounded-xl"
          >
            <div class="font-bold text-gray-900 mb-2">{{ tool.name }}</div>
            <div class="text-gray-500 text-xs">{{ tool.description }}</div>
            <div v-if="tool.inputs?.length > 0" class="">
              <div class="flex items-center gap-2 my-4">
                <div class="text-xs font-bold text-gray-500">参数</div>
                <hr class="flex-1" />
              </div>
              <div class="flex flex-col gap-4">
                <div v-for="input in tool.inputs" :key="input.name" class="flex flex-col gap-2">
                  <div class="flex items-center gap-2 text-xs">
                    <div class="text-gray-900 font-bold">{{ input.name }}</div>
                    <div class="text-gray-500">{{ typeMap[input.type] }}</div>
                    <div v-if="input.required" class="text-red-700">必填</div>
                  </div>
                  <div class="text-xs text-gray-500">{{ input.description }}</div>
                </div>
              </div>
            </div>
          </a-card>
        </div>
      </div>
    </a-drawer>

    <a-modal
      :width="630"
      :visible="props.createType === 'tool' || showOpenApiUpdateModal"
      hide-title
      :footer="false"
      modal-class="rounded-xl"
      @cancel="handleCancel"
    >
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">
          {{ props.createType === 'tool' ? '新建' : '更新' }} OpenAPI 插件
        </div>
        <a-button type="text" class="!text-gray-700" size="small" @click="handleCancel">
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <div class="pt-6">
        <a-form ref="openApiFormRef" :model="openApiForm" @submit="handleSubmitOpenApi" layout="vertical">
          <a-form-item field="fileList" hide-label :rules="[{ required: true, message: '插件图标不能为空' }]">
            <a-upload
              v-model:file-list="openApiForm.fileList"
              :limit="1"
              list-type="picture-card"
              accept="image/png, image/jpeg"
              class="!w-auto mx-auto"
              image-preview
              :custom-request="
                (option) => {
                  const uploadTask = async () => {
                    const { fileItem, onSuccess } = option
                    const uploadedImageUrl = await handleUploadImage(fileItem.file as File)
                    openApiForm.icon = uploadedImageUrl
                    onSuccess(uploadedImageUrl)
                  }
                  uploadTask()
                  return {}
                }
              "
              :on-before-remove="
                async () => {
                  openApiForm.icon = ''
                  return true
                }
              "
            />
          </a-form-item>
          <a-form-item
            field="name"
            label="插件名称"
            asterisk-position="end"
            :rules="[{ required: true, message: '插件名称不能为空' }]"
          >
            <a-input v-model="openApiForm.name" placeholder="请输入插件名称，确保名称含义清晰" show-word-limit :max-length="60" />
          </a-form-item>
          <a-form-item
            field="openapi_schema"
            label="OpenAPI Schema"
            asterisk-position="end"
            :rules="[{ required: true, message: 'OpenAPI Schema不能为空' }]"
          >
            <a-textarea
              v-model="openApiForm.openapi_schema"
              :auto-size="{ minRows: 4, maxRows: 6 }"
              placeholder="在此处输入您的 OpenAPI Schema"
              @blur="
                () => {
                  if (openApiForm.openapi_schema.trim() !== '') handleValidateOpenAPISchema(openApiForm.openapi_schema)
                }
              "
            />
          </a-form-item>
          <a-form-item label="可用工具">
            <div class="rounded-lg border border-gray-200 w-full overflow-x-auto">
              <table class="w-full leading-[18px] text-xs text-gray-700 font-normal">
                <thead class="text-gray-500">
                  <tr class="border-b border-gray-200">
                    <th class="p-2 pl-3 font-medium">名称</th>
                    <th class="p-2 pl-3 font-medium w-[236px]">描述</th>
                    <th class="p-2 pl-3 font-medium">方法</th>
                    <th class="p-2 pl-3 font-medium">路径</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(tool, idx) in apiToolsPreview" :key="idx" class="border-b last:border-0 border-gray-200 text-gray-700">
                    <td class="p-2 pl-3">{{ tool.name }}</td>
                    <td class="p-2 pl-3 w-[236px]">{{ tool.description }}</td>
                    <td class="p-2 pl-3">{{ tool.method }}</td>
                    <td class="p-2 pl-3 w-[62px]">{{ tool.path }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </a-form-item>
          <a-form-item label="Headers">
            <div class="rounded-lg border border-gray-200 w-full overflow-x-auto">
              <table class="w-full leading-[18px] text-xs text-gray-700 font-normal mb-3">
                <thead class="text-gray-500">
                  <tr class="border-b border-gray-200">
                    <th class="p-2 pl-3 font-medium">Key</th>
                    <th class="p-2 pl-3 font-medium">Value</th>
                    <th class="p-2 pl-3 font-medium w-[50px]">操作</th>
                  </tr>
                </thead>
                <tbody v-if="openApiForm.headers.length > 0" class="border-b border-gray-200">
                  <tr v-for="(header, idx) in openApiForm.headers" :key="idx" class="border-b last:border-0 border-gray-200">
                    <td class="p-2 pl-3">
                      <a-form-item :field="`headers[${idx}].key`" hide-label class="m-0">
                        <a-input v-model="header.key" placeholder="请输入请求头键名" />
                      </a-form-item>
                    </td>
                    <td class="p-2 pl-3">
                      <a-form-item :field="`headers[${idx}].value`" hide-label class="m-0">
                        <a-input v-model="header.value" placeholder="请输入请求头键值内容" />
                      </a-form-item>
                    </td>
                    <td class="p-2 pl-3">
                      <a-button size="mini" type="text" class="!text-gray-700" @click="openApiForm.headers.splice(idx, 1)">
                        <template #icon>
                          <icon-delete />
                        </template>
                      </a-button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <a-button size="mini" class="rounded ml-3 mb-3 !text-gray-700" @click="openApiForm.headers.push({ key: '', value: '' })">
                <template #icon>
                  <icon-plus />
                </template>
                增加参数
              </a-button>
            </div>
          </a-form-item>
          <div class="flex items-center justify-between">
            <a-button v-if="showOpenApiUpdateModal" class="rounded-lg !text-red-700" @click="handleDelete">
              删除
            </a-button>
            <div v-else></div>
            <a-space :size="16">
              <a-button class="rounded-lg" @click="handleCancel">取消</a-button>
              <a-button
                :loading="updateApiToolProviderLoading || createApiToolProviderLoading"
                type="primary"
                html-type="submit"
                class="rounded-lg"
              >
                保存
              </a-button>
            </a-space>
          </div>
        </a-form>
      </div>
    </a-modal>

    <a-modal
      :width="700"
      :visible="props.createType === 'mcp_tool' || showMcpUpdateModal"
      hide-title
      :footer="false"
      modal-class="rounded-xl"
      @cancel="handleCancel"
    >
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">
          {{ props.createType === 'mcp_tool' ? '添加新的' : '更新' }} MCP 服务器
        </div>
        <a-button type="text" class="!text-gray-700" size="small" @click="handleCancel">
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <div class="pt-6">
        <a-form ref="mcpFormRef" :model="mcpForm" @submit="handleSubmitMcp" layout="vertical">
          <a-form-item
            field="mcp_schema"
            label="MCP JSON 配置"
            asterisk-position="end"
            :rules="[{ required: true, message: 'MCP JSON配置不能为空' }]"
          >
            <a-textarea
              v-model="mcpForm.mcp_schema"
              :auto-size="{ minRows: 12, maxRows: 18 }"
              placeholder="粘贴包含 mcpServers 的 JSON 配置，仅支持 Streamable HTTP"
              @blur="
                () => {
                  if (mcpForm.mcp_schema.trim() !== '') handleValidateMcpSchema(mcpForm.mcp_schema)
                }
              "
            />
          </a-form-item>
          <a-form-item label="服务器与工具">
            <a-spin :loading="validateMcpSchemaLoading" class="block w-full">
            <div class="rounded-lg border border-gray-200 w-full overflow-x-auto">
              <table class="w-full leading-[18px] text-xs text-gray-700 font-normal">
                <thead class="text-gray-500">
                  <tr class="border-b border-gray-200">
                    <th class="p-2 pl-3 font-medium">服务器</th>
                    <th class="p-2 pl-3 font-medium">传输</th>
                    <th class="p-2 pl-3 font-medium w-[260px]">地址</th>
                    <th class="p-2 pl-3 font-medium">工具数</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="server in mcpServersPreview" :key="server.name" class="border-b last:border-0 border-gray-200 text-gray-700">
                    <td class="p-2 pl-3">{{ server.name }}</td>
                    <td class="p-2 pl-3">{{ server.config?.transport }}</td>
                    <td class="p-2 pl-3 w-[260px] break-all">{{ server.config?.url }}</td>
                    <td class="p-2 pl-3">{{ server.tools?.length ?? 0 }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            </a-spin>
          </a-form-item>
          <div class="flex items-center justify-between">
            <a-button v-if="showMcpUpdateModal" class="rounded-lg !text-red-700" @click="handleDelete">
              删除
            </a-button>
            <div v-else></div>
            <a-space :size="16">
              <a-button class="rounded-lg" @click="handleCancel">取消</a-button>
              <a-button
                :loading="updateMcpToolProviderLoading || createMcpToolProviderLoading"
                type="primary"
                html-type="submit"
                class="rounded-lg"
              >
                {{ showMcpUpdateModal ? '更新' : '添加' }}
              </a-button>
            </a-space>
          </div>
        </a-form>
      </div>
    </a-modal>
  </a-spin>
</template>

<style scoped></style>
