import { type BaseResponse } from '@/models/base'

export type UserModelType = 'chat' | 'embedding'

export type UserModelItem = {
  id: string
  name: string
  model_type: UserModelType
  provider: string
  base_url: string
  model_serve_name: string
  context_window: number | null
  max_length: number | null
  dimension: number | null
  features: string[]
  parameters: Record<string, any>
  is_default: boolean
  has_api_key: boolean
  created_at: number
  updated_at: number
}

export type CreateUserModelRequest = {
  name: string
  model_type: UserModelType
  base_url: string
  api_key: string
  model_serve_name: string
  context_window?: number | null
  max_length?: number | null
  dimension?: number | null
  features?: string[]
  parameters?: Record<string, any>
  is_default?: boolean
  verify?: boolean
}

export type UpdateUserModelRequest = {
  name?: string
  base_url?: string
  api_key?: string
  model_serve_name?: string
  context_window?: number | null
  max_length?: number | null
  dimension?: number | null
  features?: string[]
  parameters?: Record<string, any>
  is_default?: boolean
  verify?: boolean
}

export type ProbeUserModelRequest = {
  base_url: string
  api_key?: string
  model_type?: UserModelType
}

export type GetUserModelsResponse = BaseResponse<UserModelItem[]>
export type UserModelResponse = BaseResponse<UserModelItem>
export type ProbeUserModelResponse = BaseResponse<{ models: { id: string }[] }>
