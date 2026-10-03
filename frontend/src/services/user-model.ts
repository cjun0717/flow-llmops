import { get, post } from '@/utils/request'
import type {
  CreateUserModelRequest,
  GetUserModelsResponse,
  ProbeUserModelRequest,
  ProbeUserModelResponse,
  UpdateUserModelRequest,
  UserModelResponse,
  UserModelType,
} from '@/models/user-model'
import { type BaseResponse } from '@/models/base'

export const getUserModels = (model_type?: UserModelType | '') => {
  return get<GetUserModelsResponse>(`/user-models`, {
    params: model_type ? { model_type } : {},
  })
}

export const createUserModel = (req: CreateUserModelRequest) => {
  return post<UserModelResponse>(`/user-models`, { body: req })
}

export const updateUserModel = (model_id: string, req: UpdateUserModelRequest) => {
  return post<UserModelResponse>(`/user-models/${model_id}`, { body: req })
}

export const setDefaultUserModel = (model_id: string) => {
  return post<UserModelResponse>(`/user-models/${model_id}/default`)
}

export const deleteUserModel = (model_id: string) => {
  return post<BaseResponse<Record<string, never>>>(`/user-models/${model_id}/delete`)
}

export const probeUserModel = (req: ProbeUserModelRequest) => {
  return post<ProbeUserModelResponse>(`/user-models/probe`, { body: req })
}
