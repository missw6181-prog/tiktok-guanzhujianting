<script setup>
import { h, onMounted, ref } from 'vue'
import {
  useMessage, useDialog, NCard, NButton, NDataTable, NInput, NModal, NSpace, NTag, NTooltip, NSelect,
} from 'naive-ui'
import api from '../api'
import { apiError } from '../apiError'

const message = useMessage()
const dialog = useDialog()
const list = ref([])
const userOptions = ref([])
const userSelectOptions = ref([])
const showCreate = ref(false)
const showEdit = ref(false)
const editingId = ref(null)
const refreshingId = ref(null)
const form = ref({ user_id: null, label: '', sign_api_key: '' })
const editForm = ref({ user_id: null, label: '' })

function mapUserOptions(rows) {
  userSelectOptions.value = rows.map((u) => ({
    label: `${u.email} (#${u.id})`,
    value: u.id,
    disabled: u.status !== 'active',
  }))
}

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
  { title: 'ID', key: 'id', width: 60 },
  { title: '所属用户', key: 'user_email', minWidth: 160 },
  { title: '备注', key: 'label', width: 100, render: (row) => row.label || '-' },
  {
    title: 'API Key',
    key: 'sign_api_key',
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'mono-text' }, row.sign_api_key),
  },
  {
    title: '状态',
    key: 'in_use',
    width: 90,
    render: (row) => h(
      NTag,
      { type: row.in_use ? 'warning' : 'success', bordered: false },
      { default: () => (row.in_use ? '使用中' : '空闲') }
    ),
  },
  {
    title: '今日剩余',
    key: 'rate_limits',
    width: 120,
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
    minWidth: 140,
    render: (row) => (row.usage ? `#${row.usage.task_id} @${row.usage.streamer_unique_id}` : '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    render: (row) => h(NSpace, null, {
      default: () => [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, {
          size: 'small',
          loading: refreshingId.value === row.id,
          onClick: () => refresh(row.id),
        }, { default: () => '刷新配额' }),
        h(NButton, {
          size: 'small',
          type: 'error',
          disabled: row.in_use,
          onClick: () => remove(row),
        }, { default: () => '删除' }),
      ],
    }),
  },
]

async function loadUsers() {
  const { data } = await api.get('/admin/api/user-options')
  userOptions.value = data
  mapUserOptions(data)
}

async function load() {
  try {
    const { data } = await api.get('/admin/api/sign-keys')
    list.value = data
  } catch (e) {
    message.error(apiError(e, '加载失败'))
  }
}

async function loadAll() {
  await Promise.all([loadUsers(), load()])
}

function openCreate() {
  form.value = {
    user_id: userOptions.value.find((u) => u.status === 'active')?.id ?? null,
    label: '',
    sign_api_key: '',
  }
  showCreate.value = true
}

async function create() {
  if (!form.value.user_id) {
    message.warning('请选择所属用户')
    return
  }
  if (!form.value.sign_api_key.trim()) {
    message.warning('请填写 API Key')
    return
  }
  try {
    await api.post('/admin/api/sign-keys', {
      user_id: form.value.user_id,
      label: form.value.label.trim() || null,
      sign_api_key: form.value.sign_api_key.trim(),
    })
    message.success('已添加')
    showCreate.value = false
    await load()
  } catch (e) {
    message.error(apiError(e, '添加失败'))
  }
}

function openEdit(row) {
  editingId.value = row.id
  editForm.value = { user_id: row.user_id, label: row.label || '' }
  showEdit.value = true
}

async function saveEdit() {
  try {
    await api.patch(`/admin/api/sign-keys/${editingId.value}`, {
      user_id: editForm.value.user_id,
      label: editForm.value.label.trim() || null,
    })
    message.success('已保存')
    showEdit.value = false
    await load()
  } catch (e) {
    message.error(apiError(e, '保存失败'))
  }
}

async function refresh(id) {
  refreshingId.value = id
  try {
    await api.post(`/admin/api/sign-keys/${id}/refresh-limits`)
    message.success('配额已刷新')
    await load()
  } catch (e) {
    message.error(apiError(e, '刷新失败'))
  } finally {
    refreshingId.value = null
  }
}

function remove(row) {
  dialog.warning({
    title: '删除 API Key',
    content: `确定删除 Key ${row.sign_api_key}？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.delete(`/admin/api/sign-keys/${row.id}`)
        message.success('已删除')
        await load()
      } catch (e) {
        message.error(apiError(e, '删除失败'))
      }
    },
  })
}

onMounted(loadAll)
</script>

<template>
  <div class="page-container">
    <div class="page-header card-header-row">
      <div>
        <h1>API Key</h1>
        <p>全平台 {{ list.length }} 个 Key · 含所属用户与剩余配额</p>
      </div>
      <NButton type="primary" @click="openCreate">添加 Key</NButton>
    </div>

    <NCard class="scifi-card table-scroll" :bordered="false">
      <NDataTable :columns="columns" :data="list" :bordered="false" :scroll-x="1200" />
    </NCard>

    <NModal v-model:show="showCreate" preset="card" title="添加 API Key" style="max-width:520px">
      <NSpace vertical :size="12">
        <NSelect v-model:value="form.user_id" :options="userSelectOptions" placeholder="所属用户" />
        <NInput v-model:value="form.label" placeholder="备注（可选）" />
        <NInput v-model:value="form.sign_api_key" placeholder="Euler API Key" />
      </NSpace>
      <template #footer>
        <NButton @click="showCreate = false">取消</NButton>
        <NButton type="primary" @click="create">添加</NButton>
      </template>
    </NModal>

    <NModal v-model:show="showEdit" preset="card" title="编辑 API Key" style="max-width:480px">
      <NSpace vertical :size="12">
        <NSelect v-model:value="editForm.user_id" :options="userSelectOptions" placeholder="所属用户" />
        <NInput v-model:value="editForm.label" placeholder="备注" />
      </NSpace>
      <template #footer>
        <NButton @click="showEdit = false">取消</NButton>
        <NButton type="primary" @click="saveEdit">保存</NButton>
      </template>
    </NModal>
  </div>
</template>
