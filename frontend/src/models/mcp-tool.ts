import { type BasePaginatorResponse, type BaseResponse } from '@/models/base'

export type McpToolProvider = {
  id: string
  name: string
  description: string
  transport: string
  url: string
  headers: Record<string, string>
  tools: Array<any>
  updated_at: number
  created_at: number
}

export type GetMcpToolProvidersWithPageResponse = BasePaginatorResponse<McpToolProvider>

export type CreateMcpToolProviderRequest = {
  mcp_schema: string
}

export type UpdateMcpToolProviderRequest = {
  mcp_schema: string
}

export type GetMcpToolProviderResponse = BaseResponse<
  McpToolProvider & {
    config: Record<string, any>
    mcp_schema: string
  }
>

export type GetMcpToolResponse = BaseResponse<{
  id: string
  name: string
  description: string
  input_schema: Record<string, any>
  metadata: Record<string, any>
  provider: {
    id: string
    name: string
    label: string
    icon: string
    description: string
    transport: string
    url: string
    headers: Record<string, string>
  }
  inputs: {
    type: string
    name: string
    required: boolean
    description: string
    schema: Record<string, any>
  }[]
}>
