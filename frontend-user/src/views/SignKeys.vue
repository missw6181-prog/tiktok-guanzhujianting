<script setup>
import { h, onMounted, ref } from 'vue'
import {
  useMessage, NCard, NButton, NDataTable, NInput, NModal, NSpace, NTag, NAlert, NTooltip,
  NRadioGroup, NRadio,
} from 'naive-ui'
import api from '../api'
import { apiError } from '../apiError'

const message = useMessage()
const list = ref([])
const show = ref(false)
const addMode = ref('single')
const refreshingId = ref(null)
const form = ref({ label: '', sign_api_key: '', batch_text: '' })

function formatRemaining(row) {
  const limits = row.rate_limits
  if (!limits) return '未查询'
  if (limits.daily_remaining != null) {
    const total = limits.daily_limit != null ? `/${limits.daily_limit}` : ''
    return `${limits.daily_remaining}${total} 次`
  }
  return '未查询'
}

function quotaDetail(row) {
  const limits = row.rate_limits
  if (!limits) return ''
  const parts = []
  if (limits.daily_remaining != null) {
    parts.push(`今日剩余 ${limits.daily_remaining}${limits.daily_limit != null ? ` / ${limits.daily_limit}` : ''}`)
  }
  if (limits.hour_remaining != null) {
    parts.push(`小时剩余 ${limits.hour_remaining}${limits.hour_limit != null ? ` / ${limits.hour_limit}` : ''}`)
  }
  if (limits.minute_remaining != null) {
    parts.push(`分钟剩余 ${limits.minute_remaining}${limits.minute_limit != null ? ` / ${limits.minute_limit}` : ''}`)
  }
  if (limits.day_reset_at) {
    parts.push(`日配额重置: ${limits.day_reset_at}`)
  }
  return parts.join(' · ')
}

const columns = [
  { title: '备注', key: 'label', width: 120, render: (row) => row.label || '-' },
  {
    title: 'API Key',
    key: 'sign_api_key',
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'mono-text' }, row.sign_api_key),
  },
  {
    title: '状态',
    key: 'in_use',
    width: 100,
    render: (row) => h(
      NTag,
      { type: row.in_use ? 'warning' : 'success', bordered: false },
      { default: () => (row.in_use ? '使用中' : '空闲') }
    ),
  },
  {
    title: '今日剩余',
    key: 'rate_limits',
    width: 140,
    render: (row) => {
      const detail = quotaDetail(row)
      const text = formatRemaining(row)
      if (!detail) return text
      return h(NTooltip, { placement: 'top' }, {
        trigger: () => h('span', null, text),
        default: () => detail,
      })
    },
  },
  {
    title: '占用任务',
    key: 'usage',
    minWidth: 160,
    render: (row) => (row.usage ? `#${row.usage.task_id} @${row.usage.streamer_unique_id}` : '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    render: (row) => h(NSpace, null, {
      default: () => [
        h(NButton, {
          size: 'small',
          loading: refreshingId.value === row.id,
          onClick: () => refresh(row.id),
        }, { default: () => '刷新配额' }),
        h(NButton, {
          size: 'small',
          type: 'error',
          disabled: row.in_use,
          onClick: () => remove(row.id),
        }, { default: () => '删除' }),
      ],
    }),
  },
]

async function loadAll() {
  try {
    const { data } = await api.get('/api/sign-keys')
    list.value = data
  } catch (e) {
    message.error(apiError(e, '加载失败'))
  }
}

function openDialog() {
  addMode.value = 'single'
  form.value = { label: '', sign_api_key: '', batch_text: '' }
  show.value = true
}

async function create() {
  if (addMode.value === 'batch') {
    await createBatch()
    return
  }
  if (!form.value.sign_api_key.trim()) {
    message.warning('请填写 API Key')
    return
  }
  try {
    await api.post('/api/sign-keys', {
      label: form.value.label.trim() || null,
      sign_api_key: form.value.sign_api_key.trim(),
    })
    message.success('已添加到 Key 池')
    show.value = false
    await loadAll()
  } catch (e) {
    message.error(apiError(e, '添加失败'))
  }
}

async function createBatch() {
  const keys = form.value.batch_text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  if (!keys.length) {
    message.warning('请粘贴至少一行 API Key')
    return
  }
  try {
    const { data } = await api.post('/api/sign-keys/batch', {
      sign_api_keys: keys,
      label: form.value.label.trim() || null,
    })
    const failCount = data.failed?.length || 0
    if (data.imported > 0) {
      message.success(`成功添加 ${data.imported} 个 Key${failCount ? `，${failCount} 个失败` : ''}`)
    } else {
      message.warning(`全部失败（${failCount} 个）`)
    }
    if (failCount) {
      const detail = data.failed.slice(0, 3).map((f) => `${f.sign_api_key}: ${f.reason}`).join('；')
      message.warning(detail)
    }
    if (data.imported > 0) {
      show.value = false
      await loadAll()
    }
  } catch (e) {
    message.error(apiError(e, '批量添加失败'))
  }
}

async function refresh(id) {
  refreshingId.value = id
  try {
    await api.post(`/api/sign-keys/${id}/refresh-limits`)
    message.success('配额已刷新')
    await loadAll()
  } catch (e) {
    message.error(apiError(e, '刷新失败'))
  } finally {
    refreshingId.value = null
  }
}

async function remove(id) {
  try {
    await api.delete(`/api/sign-keys/${id}`)
    message.success('已删除')
    await loadAll()
  } catch (e) {
    message.error(apiError(e, '删除失败'))
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="page-container">
    <NAlert
      type="info"
      :show-icon="true"
      title="API Key 是什么？"
      class="intro scifi-card"
      style="margin-bottom: 16px"
    >
      监听 TikTok 直播间需要先获取「签名连接地址」，本系统通过 Euler Stream 完成这一步。每个 API Key 对应一份每日连接配额。
      每个 Key 全局只能绑定一个监控任务；配额约 1000 次/天。
      申请地址：
      <a href="https://www.eulerstream.com/pricing" target="_blank" rel="noopener noreferrer">eulerstream.com/pricing</a>
    </NAlert>

    <div class="page-header card-header-row">
      <div>
        <h1>API Key 池</h1>
        <p>共 {{ list.length }} 个 Key</p>
      </div>
      <NButton type="primary" @click="openDialog">添加 Key</NButton>
    </div>

    <NCard class="scifi-card table-scroll" :bordered="false">
      <NDataTable :columns="columns" :data="list" :bordered="false" :scroll-x="1000" />
    </NCard>

    <NModal v-model:show="show" preset="card" title="添加 API Key" style="max-width:560px">
      <NSpace vertical :size="12">
        <NRadioGroup v-model:value="addMode">
          <NSpace>
            <NRadio value="single">单个添加</NRadio>
            <NRadio value="batch">批量添加</NRadio>
          </NSpace>
        </NRadioGroup>
        <NInput v-model:value="form.label" placeholder="备注（可选，批量时应用于全部 Key）" />
        <NInput
          v-if="addMode === 'single'"
          v-model:value="form.sign_api_key"
          placeholder="粘贴 Euler 控制台创建的 API Key"
        />
        <NInput
          v-else
          v-model:value="form.batch_text"
          type="textarea"
          :rows="8"
          placeholder="每行一个 API Key"
        />
        <div class="hint-text">
          在
          <a href="https://www.eulerstream.com/pricing" target="_blank" rel="noopener noreferrer">Euler Stream</a>
          注册并创建 Key 后粘贴。每个 Key 全局只能使用一次。
        </div>
      </NSpace>
      <template #footer>
        <NButton @click="show = false">取消</NButton>
        <NButton type="primary" @click="create">{{ addMode === 'batch' ? '批量添加' : '添加' }}</NButton>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.intro :deep(a) { color: #00f0ff; }
</style>
