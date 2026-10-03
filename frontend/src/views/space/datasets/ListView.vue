<script setup lang="ts">
import {computed, onMounted, watch} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import moment from 'moment'
import type {ValidatedError} from '@arco-design/web-vue'
import {useCreateOrUpdateDataset, useDeleteDataset, useGetDataset, useGetDatasetsWithPage,} from '@/hooks/use-dataset'
import {useAccountStore} from '@/stores/account'
import {useUploadImage} from '@/hooks/use-upload-file'
import {useGetUserModels} from '@/hooks/use-user-model'

// 1.定义页面所需数据
const route = useRoute()
const router = useRouter()
const accountStore = useAccountStore()
const props = defineProps({
  createType: {type: String, required: true},
})
const emits = defineEmits(['update:create-type'])
let updateDatasetID = ''
const {dataset, loadDataset} = useGetDataset()
const {loading, datasets, paginator, loadDatasets} = useGetDatasetsWithPage()
const {image_url, handleUploadImage} = useUploadImage()
const {
  loading: submitLoading,
  form,
  formRef,
  saveDataset,
  showUpdateModal,
  updateShowUpdateModal,
} = useCreateOrUpdateDataset()
const {handleDelete} = useDeleteDataset()
const {user_models: embeddingModels, loadUserModels: loadEmbeddingModels} = useGetUserModels()
const isCreate = computed(() => props.createType === 'dataset')
const embeddingOptions = computed(() =>
  embeddingModels.value.map((item) => ({
    label: item.is_default ? `${item.name}（默认）` : `${item.name} · ${item.dimension || '-'} 维`,
    value: item.id,
  })),
)
const search_word = computed(() => {
  return String(route.query?.search_word ?? '')
})

// 2.定义滚动数据分页处理器
const handleScroll = async (event: UIEvent) => {
  // 2.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const {scrollTop, scrollHeight, clientHeight} = event.target as HTMLElement

  // 2.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (loading.value) return
    await loadDatasets(false, search_word.value)
  }
}

// 3.定义编辑知识库处理器
const handleUpdate = (dataset_id: string) => {
  updateShowUpdateModal(true, async () => {
    // 1.调用api获取知识库详情
    await loadDataset(dataset_id)
    updateDatasetID = dataset_id

    // 2.更新表单数据
    formRef.value?.resetFields()
    form.value.fileList = [{uid: '1', name: '知识库图标', url: dataset.value.icon}]
    form.value.icon = dataset.value.icon
    form.value.name = dataset.value.name
    form.value.description = dataset.value.description
    form.value.embedding_model_id = dataset.value.embedding_model_id || ''
    form.value.embedding_model_name = dataset.value.embedding_model_name || ''
  })
}

// 4.定义取消显示模态窗
const handleCancel = () => {
  updateShowUpdateModal(false, async () => {
    // 1.重置整个表单数据
    updateDatasetID = ''
    formRef.value?.resetFields()

    // 2.隐藏表单模态窗
    emits('update:create-type', '')
  })
}

// 5.定义提交模态窗处理器
const handleSubmit = async ({errors}: { errors: Record<string, ValidatedError> | undefined }) => {
  // 1.如果出错则直接抛出
  if (errors) return

  // 2.调用保存知识库服务
  await saveDataset(updateDatasetID)

  // 3.关闭模态窗并且刷新数据
  handleCancel()
  await loadDatasets(true)
}

// 6.监听路由query的变化
watch(
    () => route.query?.search_word,
    (newValue) => loadDatasets(true, String(newValue)),
)

// 7.页面DOM加载后加载数据
watch(
    () => props.createType,
    (newValue) => {
      if (newValue === 'dataset') {
        const def = embeddingModels.value.find((item) => item.is_default) || embeddingModels.value[0]
        if (def) form.value.embedding_model_id = def.id
      }
    },
)

onMounted(() => {
  loadDatasets(true, search_word.value)
  loadEmbeddingModels('embedding')
})
</script>

<template>
  <a-spin
      :loading="loading"
      class="block h-full w-full scrollbar-w-none overflow-scroll"
      @scroll="handleScroll"
  >
    <!-- 底部知识库列表 -->
    <a-row :gutter="[20, 20]" class="flex-1">
      <!-- 有数据的UI状态 -->
      <a-col v-for="dataset in datasets" :key="dataset.id" :span="6">
        <div
          class="cursor-pointer"
          @click="
            router.push({
              name: 'space-datasets-documents-list',
              params: { dataset_id: dataset.id },
            })
          "
        >
        <a-card hoverable class="rounded-lg">
          <!-- 顶部知识库名称 -->
          <div class="flex items-center gap-3 mb-3">
            <!-- 左侧图标 -->
            <a-avatar :size="40" shape="square" class="rounded-lg flex-shrink-0" :image-url="dataset.icon"/>
            <!-- 右侧知识库信息 -->
            <div class="flex flex-1 min-w-0 justify-between">
              <div class="flex flex-col min-w-0">
                <router-link
                    :to="{
                    name: 'space-datasets-documents-list',
                    params: { dataset_id: dataset.id },
                  }"
                    class="text-base text-gray-900 font-bold line-clamp-1 break-all"
                >{{ dataset.name }}
                </router-link>
                <div class="text-xs text-gray-500 line-clamp-1">
                  {{ dataset.document_count }} 文档 ·
                  {{ Math.round(dataset.character_count / 1000) }} 千字符 ·
                  {{ dataset.related_app_count }} 关联应用
                </div>
              </div>
              <!-- 操作按钮 -->
              <div @click.stop>
              <a-dropdown position="br">
                <a-button type="text" size="small" class="rounded-lg !text-gray-700 flex-shrink-0">
                  <template #icon>
                    <icon-more/>
                  </template>
                </a-button>
                <template #content>
                  <a-doption @click="() => handleUpdate(dataset.id)">设置</a-doption>
                  <a-doption
                      class="!text-red-500"
                      @click="() => handleDelete(dataset.id, () => loadDatasets(true))"
                  >
                    删除
                  </a-doption>
                </template>
              </a-dropdown>
              </div>
            </div>
          </div>
          <!-- 知识库的描述信息 -->
          <div class="leading-[18px] text-gray-500 h-[72px] line-clamp-4 mb-2 break-all">
            {{ dataset.description }}
          </div>
          <!-- 知识库的归属者信息 -->
          <div class="flex items-center gap-1.5">
            <a-avatar :size="18" class="bg-blue-700">
              <icon-user/>
            </a-avatar>
            <div class="text-xs text-gray-400">
              {{ accountStore.account.name }} · 最近编辑
              {{ moment(dataset.updated_at * 1000).format('MM-DD HH:mm') }}
            </div>
          </div>
        </a-card>
        </div>
      </a-col>
      <!-- 没数据的UI状态 -->
      <a-col v-if="datasets.length === 0" :span="24">
        <a-empty
            description="没有可用的知识库"
            class="h-[400px] flex flex-col items-center justify-center"
        />
      </a-col>
    </a-row>
    <!-- 加载器 -->
    <a-row v-if="paginator.total_page >= 2">
      <!-- 加载数据中 -->
      <a-col v-if="paginator.current_page <= paginator.total_page" :span="24" align="center">
        <a-space class="my-4">
          <a-spin/>
          <div class="text-gray-400">加载中</div>
        </a-space>
      </a-col>
      <!-- 数据加载完成 -->
      <a-col v-else :span="24" align="center">
        <div class="text-gray-400 my-4">数据已加载完成</div>
      </a-col>
    </a-row>
    <!-- 新建/修改模态窗 -->
    <a-modal
        :width="520"
        :visible="props.createType === 'dataset' || showUpdateModal"
        hide-title
        :footer="false"
        modal-class="rounded-xl"
        @cancel="handleCancel"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">
          {{ props.createType === 'dataset' ? '新建' : '更新' }}知识库
        </div>
        <a-button type="text" class="!text-gray-700" size="small" @click="handleCancel">
          <template #icon>
            <icon-close/>
          </template>
        </a-button>
      </div>
      <!-- 中间表单 -->
      <div class="pt-6">
        <a-form ref="formRef" :model="form" @submit="handleSubmit" layout="vertical">
          <a-form-item
              field="fileList"
              hide-label
              :rules="[{ required: true, message: '知识库图标不能为空' }]"
          >
            <a-upload
                :limit="1"
                list-type="picture-card"
                accept="image/png, image/jpeg"
                class="!w-auto mx-auto"
                v-model:file-list="form.fileList"
                image-preview
                :custom-request="
                (option) => {
                  // 1.从option中获取数据
                  const { fileItem, onSuccess, onError } = option

                  // 2.使用普通异步函数完成上传
                  const uploadTask = async () => {
                    try {
                      const uploadedImageUrl = await handleUploadImage(fileItem.file as File)
                      form.icon = uploadedImageUrl
                      onSuccess(uploadedImageUrl)
                    } catch (error) {
                      onError(error)
                    }
                  }
                  uploadTask()

                  return { abort: () => {} }
                }
              "
                :on-before-remove="
                async () => {
                  form.icon = ''
                  return true
                }
              "
            />
          </a-form-item>
          <a-form-item
              field="name"
              label="知识库名称"
              asterisk-position="end"
              :rules="[{ required: true, message: '知识库名称不能为空' }]"
          >
            <a-input
                v-model="form.name"
                placeholder="请输入知识库名称"
                show-word-limit
                :max-length="60"
            />
          </a-form-item>
          <a-form-item field="description" label="知识库描述" asterisk-position="end">
            <a-textarea
                v-model="form.description"
                :auto-size="{ minRows: 4, maxRows: 6 }"
                placeholder="请输入知识库内容的描述"
            />
          </a-form-item>
          <a-form-item
              field="embedding_model_id"
              label="向量模型"
              asterisk-position="end"
              :rules="isCreate ? [{ required: true, message: '请选择向量模型' }] : []"
          >
            <a-select
                v-if="isCreate"
                v-model="form.embedding_model_id"
                :options="embeddingOptions"
                placeholder="请选择向量模型，创建后不可更改"
                allow-search
            />
            <a-input v-else :model-value="form.embedding_model_name || '未绑定（将使用账号默认向量模型）'" disabled />
            <div v-if="isCreate && embeddingModels.length === 0" class="text-xs text-gray-500 mt-1">
              请先到模型管理添加向量模型后再创建知识库
            </div>
          </a-form-item>
          <!-- 底部按钮 -->
          <div class="flex items-center justify-between">
            <div class=""></div>
            <a-space :size="16">
              <a-button class="rounded-lg" @click="handleCancel">取消</a-button>
              <a-button
                  :loading="submitLoading"
                  type="primary"
                  html-type="submit"
                  class="rounded-lg"
                  :disabled="isCreate && embeddingModels.length === 0"
              >
                保存
              </a-button>
            </a-space>
          </div>
        </a-form>
      </div>
    </a-modal>
  </a-spin>
</template>

<style scoped></style>
