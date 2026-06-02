import { get, post } from '@/utils/request'
import { type BaseResponse } from '@/models/base'
import {
  type CreateMcpToolProviderRequest,
  type GetMcpToolProviderResponse,
  type GetMcpToolProvidersWithPageResponse,
  type GetMcpToolResponse,
  type UpdateMcpToolProviderRequest,
} from '@/models/mcp-tool'

export const getMcpToolProvidersWithPage = (
  current_page: number = 1,
  page_size: number = 20,
  search_word: string = '',
) => {
  return get<GetMcpToolProvidersWithPageResponse>('/mcp-tools', {
    params: { current_page, page_size, search_word },
  })
}

export const validateMcpSchema = (mcp_schema: string) => {
  return post<BaseResponse<any>>('/mcp-tools/validate-mcp-schema', {
    body: { mcp_schema },
  })
}

export const createMcpToolProvider = (req: CreateMcpToolProviderRequest) => {
  return post<BaseResponse<any>>('/mcp-tools', { body: req })
}

export const updateMcpToolProvider = (
  provider_id: string,
  req: UpdateMcpToolProviderRequest,
) => {
  return post<BaseResponse<any>>(`/mcp-tools/${provider_id}`, { body: req })
}

export const deleteMcpToolProvider = (provider_id: string) => {
  return post<BaseResponse<any>>(`/mcp-tools/${provider_id}/delete`)
}

export const getMcpToolProvider = (provider_id: string) => {
  return get<GetMcpToolProviderResponse>(`/mcp-tools/${provider_id}`)
}

export const getMcpTool = (provider_id: string, tool_name: string) => {
  return get<GetMcpToolResponse>(`/mcp-tools/${provider_id}/tools/${tool_name}`)
}
