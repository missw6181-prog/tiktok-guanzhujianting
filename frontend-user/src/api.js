import axios from 'axios'
import { createDiscreteApi } from 'naive-ui'

const { message } = createDiscreteApi(['message'])

const api = axios.create({ baseURL: '' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail
    const msg = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg).join('；')
        : err.message
    message.error(typeof msg === 'string' ? msg : '请求失败')
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user_email')
      if (!location.pathname.includes('/login')) location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
