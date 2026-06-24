<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, NCard, NForm, NFormItem, NInput, NButton } from 'naive-ui'
import api from '../api'
import { apiError } from '../apiError'

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const form = ref({ email: '', password: '' })

async function submit() {
  loading.value = true
  try {
    const { data } = await api.post('/api/auth/login', form.value)
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user_email', data.email)
    message.success('登录成功')
    router.push('/overview')
  } catch (e) {
    message.error(apiError(e, '登录失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-bg" />
    <NCard class="auth-card scifi-card" :bordered="false">
      <div class="auth-header">
        <div class="auth-logo">◈</div>
        <h1 class="scifi-glow">LIVE MONITOR</h1>
        <p>用户中心</p>
      </div>
      <NForm @submit.prevent="submit">
        <NFormItem label="邮箱">
          <NInput v-model:value="form.email" size="large" />
        </NFormItem>
        <NFormItem label="密码">
          <NInput
            v-model:value="form.password"
            type="password"
            show-password-on="click"
            size="large"
            @keyup.enter="submit"
          />
        </NFormItem>
        <NButton type="primary" block size="large" :loading="loading" @click="submit">登录</NButton>
      </NForm>
    </NCard>
  </div>
</template>
