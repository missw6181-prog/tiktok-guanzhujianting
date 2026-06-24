<script setup>
import { h, onMounted, ref } from 'vue'
import {
  useMessage, useDialog, NCard, NButton, NDataTable, NInput, NModal, NSpace, NTag, NSelect, NSwitch,
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
const form = ref({ user_id: null, bot_token: '', name: '' })
const editForm = ref({ user_id: null, name: '', is_active: true, bot_token: '' })

function mapUserOptions(rows) {
  userSelectOptions.value = rows.map((u) => ({
    label: `${u.email} (#${u.id})`,
    value: u.id,
    disabled: u.status !== 'active',
  }))
}

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '所属用户', key: 'user_email', minWidth: 160 },
  { title: '名称', key: 'name', width: 120 },
  { title: 'Bot ID', key: 'bot_telegram_id', width: 130, render: (row) => row.bot_telegram_id || '-' },
  {
    title: '用户名',
    key: 'username',
    width: 130,
    render: (row) => (row.username ? `@${row.username}` : '-'),
  },
  {
    title: 'Token',
    key: 'bot_token',
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'mono-text' }, row.bot_token),
  },
  {
    title: '状态',
    key: 'is_active',
    width: 90,
    render: (row) => h(
      NTag,
      { type: row.is_active ? 'success' : 'default', bordered: false },
      { default: () => (row.is_active ? '启用' : '停用') }
    ),
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
    const { data } = await api.get('/admin/api/bots')
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
    bot_token: '',
    name: '',
  }
  showCreate.value = true
}

async function create() {
  if (!form.value.user_id) {
    message.warning('请选择所属用户')
    return
  }
  if (!form.value.bot_token.trim()) {
    message.warning('请填写 Bot Token')
    return
  }
  try {
    await api.post('/admin/api/bots', {
      user_id: form.value.user_id,
      bot_token: form.value.bot_token.trim(),
      name: form.value.name.trim() || null,
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
  editForm.value = {
    user_id: row.user_id,
    name: row.name || '',
    is_active: row.is_active,
    bot_token: '',
  }
  showEdit.value = true
}

async function saveEdit() {
  try {
    const payload = {
      user_id: editForm.value.user_id,
      name: editForm.value.name.trim() || null,
      is_active: editForm.value.is_active,
    }
    if (editForm.value.bot_token.trim()) {
      payload.bot_token = editForm.value.bot_token.trim()
    }
    await api.patch(`/admin/api/bots/${editingId.value}`, payload)
    message.success('已保存')
    showEdit.value = false
    await load()
  } catch (e) {
    message.error(apiError(e, '保存失败'))
  }
}

function remove(row) {
  dialog.warning({
    title: '删除机器人',
    content: `确定删除 ${row.name}？相关群组与任务绑定可能失效。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.delete(`/admin/api/bots/${row.id}`)
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
        <h1>机器人 Token</h1>
        <p>全平台 {{ list.length }} 个 Bot · 含所属用户</p>
      </div>
      <NButton type="primary" @click="openCreate">添加机器人</NButton>
    </div>

    <NCard class="scifi-card table-scroll" :bordered="false">
      <NDataTable :columns="columns" :data="list" :bordered="false" :scroll-x="1200" />
    </NCard>

    <NModal v-model:show="showCreate" preset="card" title="添加机器人" style="max-width:520px">
      <NSpace vertical :size="12">
        <NSelect v-model:value="form.user_id" :options="userSelectOptions" placeholder="所属用户" />
        <NInput v-model:value="form.bot_token" placeholder="从 @BotFather 获取的 Token" />
        <NInput v-model:value="form.name" placeholder="显示名称（可选，默认自动识别）" />
      </NSpace>
      <template #footer>
        <NButton @click="showCreate = false">取消</NButton>
        <NButton type="primary" @click="create">添加</NButton>
      </template>
    </NModal>

    <NModal v-model:show="showEdit" preset="card" title="编辑机器人" style="max-width:520px">
      <NSpace vertical :size="12">
        <NSelect v-model:value="editForm.user_id" :options="userSelectOptions" placeholder="所属用户" />
        <NInput v-model:value="editForm.name" placeholder="显示名称" />
        <div class="form-row">
          <span>启用</span>
          <NSwitch v-model:value="editForm.is_active" />
        </div>
        <NInput
          v-model:value="editForm.bot_token"
          type="password"
          show-password-on="click"
          placeholder="新 Token（留空不改）"
        />
      </NSpace>
      <template #footer>
        <NButton @click="showEdit = false">取消</NButton>
        <NButton type="primary" @click="saveEdit">保存</NButton>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
