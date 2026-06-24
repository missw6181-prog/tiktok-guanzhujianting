<script setup>
import { h, inject, onMounted, ref } from 'vue'
import {
  useMessage, NCard, NButton, NDataTable, NInput, NModal, NSpace,
} from 'naive-ui'
import api from '../api'
import { apiError } from '../apiError'

const me = inject('me')
const reloadMe = inject('reloadMe')
const message = useMessage()
const list = ref([])
const show = ref(false)
const form = ref({ bot_token: '' })
const previewInfo = ref(null)
const previewing = ref(false)
const saving = ref(false)

const columns = [
  { title: '名称', key: 'name' },
  { title: 'Bot ID', key: 'bot_telegram_id', width: 140, render: (row) => row.bot_telegram_id || '-' },
  {
    title: '用户名',
    key: 'username',
    width: 140,
    render: (row) => (row.username ? `@${row.username}` : '-'),
  },
  {
    title: 'Token',
    key: 'bot_token',
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'mono-text' }, row.bot_token),
  },
  { title: '创建时间', key: 'created_at' },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) => h(
      NButton,
      { size: 'small', type: 'error', onClick: () => remove(row.id) },
      { default: () => '删除' }
    ),
  },
]

function openDialog() {
  form.value = { bot_token: '' }
  previewInfo.value = null
  show.value = true
}

async function load() {
  try {
    const { data } = await api.get('/api/bots')
    list.value = data
  } catch (e) {
    message.error(apiError(e, '加载失败'))
  }
}

async function preview() {
  const token = form.value.bot_token.trim()
  if (token.length < 10) {
    previewInfo.value = null
    return
  }
  previewing.value = true
  try {
    const { data } = await api.post('/api/bots/preview', { bot_token: token })
    previewInfo.value = data
  } catch {
    previewInfo.value = null
  } finally {
    previewing.value = false
  }
}

async function create() {
  if (!previewInfo.value) {
    message.warning('请先验证 Token')
    return
  }
  saving.value = true
  try {
    await api.post('/api/bots', { bot_token: form.value.bot_token.trim() })
    message.success('已添加')
    show.value = false
    await load()
    await reloadMe()
  } catch (e) {
    message.error(apiError(e, '添加失败'))
  } finally {
    saving.value = false
  }
}

async function remove(id) {
  try {
    await api.delete(`/api/bots/${id}`)
    message.success('已删除')
    await load()
    await reloadMe()
  } catch (e) {
    message.error(apiError(e, '删除失败'))
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header card-header-row">
      <div>
        <h1>机器人</h1>
        <p>Bot ({{ list.length }}/{{ me?.max_bots || 10 }})</p>
      </div>
      <NButton type="primary" @click="openDialog">添加机器人</NButton>
    </div>

    <NCard class="scifi-card table-scroll" :bordered="false">
      <NDataTable :columns="columns" :data="list" :bordered="false" :scroll-x="900" />
    </NCard>

    <NModal v-model:show="show" preset="card" title="添加机器人" style="max-width:520px">
      <NSpace vertical :size="12">
        <NInput
          v-model:value="form.bot_token"
          placeholder="从 @BotFather 获取"
          @blur="preview"
        />
        <NButton :loading="previewing" @click="preview">验证 Token</NButton>
        <NCard v-if="previewInfo" size="small" :bordered="false" class="scifi-card">
          已识别：{{ previewInfo.display_name }} · Bot ID: {{ previewInfo.bot_telegram_id }}
          <span v-if="previewInfo.username"> · @{{ previewInfo.username }}</span>
        </NCard>
      </NSpace>
      <template #footer>
        <NButton @click="show = false">取消</NButton>
        <NButton type="primary" :loading="saving" :disabled="!previewInfo" @click="create">保存</NButton>
      </template>
    </NModal>
  </div>
</template>
