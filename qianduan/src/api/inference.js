import axios from 'axios'

const baseURL = import.meta.env.VITE_APP_BASE_API || '/api'

const apiClient = axios.create({
  baseURL,
  timeout: 30000,
})

/**
 * 检查后端服务与模型健康状态
 */
export async function checkHealth() {
  const resp = await apiClient.get('/health')
  return resp.data
}

/**
 * 获取原始 Mine 预览使用的完整基准数据。数据由后端统一提供。
 */
export async function getPreviewBootstrap() {
  const resp = await apiClient.get('/preview/bootstrap')
  return resp.data
}

/**
 * 上传批次 CSV (或单文件) 并创建异步推理任务
 * @param {File|File[]} files
 * @param {object|string|null} manifest
 */
export async function createRun(files, manifest = null) {
  const formData = new FormData()
  if (Array.isArray(files)) {
    files.forEach(f => {
      formData.append('files', f)
    })
  } else if (files instanceof FileList) {
    Array.from(files).forEach(f => {
      formData.append('files', f)
    })
  } else if (files) {
    formData.append('files', files)
    formData.append('file', files)
  }

  if (manifest) {
    formData.append('manifest', typeof manifest === 'string' ? manifest : JSON.stringify(manifest))
  }

  const resp = await apiClient.post('/runs', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 120000,
  })
  return resp.data
}

/**
 * 查询推理任务进度与状态
 * @param {string} runId
 */
export async function getRunStatus(runId) {
  const resp = await apiClient.get(`/runs/${runId}`)
  return resp.data
}

/**
 * 获取任务推理完整结果与适配前端结构
 * @param {string} runId
 */
export async function getRunResult(runId) {
  const resp = await apiClient.get(`/runs/${runId}/result`)
  return resp.data
}

