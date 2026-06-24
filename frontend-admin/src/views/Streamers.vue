<script setup>
import { h, onMounted, ref } from 'vue'
import {
  useMessage, useDialog, NCard, NButton, NDataTable, NInput, NModal, NSpace, NSelect,
} from 'naive-ui'
import api from '../api'
import { apiError } from '../apiError'

const message = useMessage()
const dialog = useDialog()
const list = ref([])
const userOptions = ref([])
const showCreate = ref(false)
const showEdit = ref(false)
const editingId = ref(null)
const form = ref({ user_id: null, unique_id: '', display_name: '' })
const editForm = ref({ user_id: null, display_name: '' })

const userSelectOptions = ref([])

function mapUserOptions(rows) {
  userSelectOptions.value = rows.map((u) => ({
    label: `${u.email} (#${u.id})`,
    value: u.id,
    disabled: u.status !== 'active',
  }))
}

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '所属用户', key: 'user_email', minWidth: 180 },
  {
    title: 'TikTok ID',
    key: 'unique_id',
    minWidth: 140,
    render: (row) => h('span', { class: 'mono-text' }, `@${row.unique_id}`),
  },
  { title: '备注名', key: 'display_name', width: 120, render: (row) => row.display_name || '-' },
  {
    title: '监控任务',
    key: 'tasks',
    width: 120,
    render: (row) => `${row.enabled_task_count}/${row.task_count} 启用`,
  },
  { title: '创建时间', key: 'created_at', width: 180 },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    render: (row) => h(NSpace, null, {
      default: () => [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => remove(row) }, { default: () => '删除' }),
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
    const { data } = await api.get('/admin/api/streamers')
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
    unique_id: '',
    display_name: '',
  }
  showCreate.value = true
}

async function create() {
  if (!form.value.user_id) {
    message.warning('请选择所属用户')
    return
  }
  if (!form.value.unique_id.trim()) {
    message.warning('请填写 TikTok unique_id')
    return
  }
  try {
    await api.post('/admin/api/streamers', {
      user_id: form.value.user_id,
      unique_id: form.value.unique_id.trim(),
      display_name: form.value.display_name.trim() || null,
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
  editForm.value = { user_id: row.user_id, display_name: row.display_name || '' }
  showEdit.value = true
}

async function saveEdit() {
  try {
    await api.patch(`/admin/api/streamers/${editingId.value}`, {
      user_id: editForm.value.user_id,
      display_name: editForm.value.display_name.trim() || null,
    })
    message.success('已保存')
    showEdit.value = false
    await load()
  } catch (e) {
    message.error(apiError(e, '保存失败'))
  }
}

function remove(row) {
  dialog.warning({
    title: '删除主播',
    content: `确定删除 @${row.unique_id}？相关监控任务将一并删除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.delete(`/admin/api/streamers/${row.id}`)
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
        <h1>监控主播</h1>
        <p>全平台 {{ list.length }} 个主播 · 含所属用户</p>
      </div>
      <NButton type="primary" @click="openCreate">添加主播</NButton>
    </div>

    <NCard class="scifi-card table-scroll" :bordered="false">
      <NDataTable :columns="columns" :data="list" :bordered="false" :scroll-x="1000" />
    </NCard>

    <NModal v-model:show="showCreate" preset="card" title="添加主播" style="max-width:480px">
      <NSpace vertical :size="12">
        <NSelect v-model:value="form.user_id" :options="userSelectOptions" placeholder="所属用户" />
        <NInput v-model:value="form.unique_id" placeholder="TikTok unique_id（不含 @）" />
        <NInput v-model:value="form.display_name" placeholder="备注名（可选）" />
      </NSpace>
      <template #footer>
        <NButton @click="showCreate = false">取消</NButton>
        <NButton type="primary" @click="create">添加</NButton>
      </template>
    </NModal>

    <NModal v-model:show="showEdit" preset="card" title="编辑主播" style="max-width:480px">
      <NSpace vertical :size="12">
        <NSelect v-model:value="editForm.user_id" :options="userSelectOptions" placeholder="所属用户" />
        <NInput v-model:value="editForm.display_name" placeholder="备注名" />
      </NSpace>
      <template #footer>
        <NButton @click="showEdit = false">取消</NButton>
        <NButton type="primary" @click="saveEdit">保存</NButton>
      </template>
    </NModal>
  </div>
</template>
