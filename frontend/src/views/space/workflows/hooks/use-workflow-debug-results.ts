import { ref } from 'vue'

export type WorkflowNodeDebugResult = {
  status: string
  outputs?: Record<string, any>
  error?: string
  latency?: number
}

const nodeDebugResults = ref<Record<string, WorkflowNodeDebugResult>>({})

export const useWorkflowDebugResults = () => {
  const clearNodeDebugResults = () => {
    nodeDebugResults.value = {}
  }

  const setNodeDebugResult = (nodeId: string, result: WorkflowNodeDebugResult) => {
    nodeDebugResults.value = {
      ...nodeDebugResults.value,
      [nodeId]: result,
    }
  }

  return {
    nodeDebugResults,
    clearNodeDebugResults,
    setNodeDebugResult,
  }
}
