import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import type { ApiResponse } from '@/types'

interface ValidationDetail { loc?: unknown[]; msg?: string }

function errorMessage(error: any): string {
  const data = error.response?.data
  if (typeof data?.message === 'string' && data.message) return data.message
  if (typeof data?.detail === 'string' && data.detail) return data.detail
  if (Array.isArray(data?.detail)) {
    const details = (data.detail as ValidationDetail[]).map((item) => {
      const field = item.loc?.filter(value => !['body', 'query', 'path'].includes(String(value))).join('.')
      return `${field ? `${field}：` : ''}${item.msg || '字段校验失败'}`
    }).filter(Boolean)
    if (details.length) return `请求参数错误：${details.join('；')}`
  }
  if (!error.response) return '无法连接后端服务，请检查后端是否启动及接口地址'
  return error.message || '网络异常，请稍后重试'
}

const request = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api', timeout: 15000 })
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('certificate_admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
request.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse<unknown>
    if (body && typeof body.code === 'number') {
      if (body.code !== 0) {
        ElMessage.error(body.message || '请求失败')
        return Promise.reject(new Error(body.message || '请求失败'))
      }
      return body.data
    }
    return response.data
  },
  (error) => {
    const message = errorMessage(error)
    if (error.response?.status === 401) {
      localStorage.removeItem('certificate_admin_token')
      localStorage.removeItem('certificate_admin_user')
      if (router.currentRoute.value.path === '/login') ElMessage.error(message)
      else {
        router.replace('/login')
        ElMessage.warning('登录已失效，请重新登录')
      }
    } else if (error.response?.status === 403) {
      ElMessage.error(message)
      router.replace('/403')
    } else {
      if (!error.config?.skipErrorMessage) ElMessage.error(message)
    }
    error.message = message
    error.__messageShown = true
    return Promise.reject(error)
  }
)
export default request