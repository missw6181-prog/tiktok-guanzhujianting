<script setup>
import { h, onMounted, ref } from 'vue'
import {
  useMessage, useDialog, NCard, NButton, NDataTable, NInput, NModal, NSpace, NTag, NSelect,
  NInputNumber,
} from 'naive-ui'
import AdminGroupsPanel from '../components/AdminGroupsPanel.vue'
import api from '../api'
import { apiError } from '../apiError'

const message = useMessage()
const dialog = useDialog()
const users = ref([])
const showCreate = ref(false)
const showEdit = ref(false)
const showGroups = ref(false)
const groupsUser = ref(null)
const editingId = ref(null)
const form = ref({ email: '', password: '', role: 'user' })
const editForm = ref({
  status: 'active',
  role: 'user',
  max_monitors: 10,
  max_bots: 10,
  max_groups: 10,
  password: '',
})

const roleOptions = [
  { label: '普通用户', value: 'user' },
  { label: '管理员', value: 'admin' },
]

const statusOptions = [
  { label: '正常', value: 'active' },
  { label: '禁用', value: 'disabled' },
]

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '邮箱', key: 'email', minWidth: 180 },
  {
    title: '密码',
    key: 'password_plain',
    width: 140,
    render: (row) => h(
      'span',
      { class: 'mono-text' },
      row.password_plain || '—'
    ),
  },
  { title: '角色', key: 'role', width: 90 },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) => h(
      NTag,
      { type: row.status === 'active' ? 'success' : 'error', bordered: false },
      { default: () => (row.status === 'active' ? '正常' : '禁用') }
    ),
  },
  {
    title: '配额',
    key: 'quota',
    minWidth: 220,
    render: (row) => `任务 ${row.monitor_count}/${row.max_monitors} · Bot ${row.max_bots} · 群 ${row.max_groups}`,
  },
  { title: '创建时间', key: 'created_at', width: 180 },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    render: (row) => h(NSpace, null, {
      default: () => [
        h(NButton, { size: 'small', onClick: () => openGroups(row) }, { default: () => '群组' }),
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => remove(row) }, { default: () => '删除' }),
      ],
    }),
  },
]

async function load() {
  try {
    const { data } = await api.get('/admin/api/users')
    users.value = data
  } catch (e) {
    message.error(apiError(e, '加载用户列表失败'))
  }
}

async function create() {
  try {
    await api.post('/admin/api/users', form.value)
    message.success('用户已创建')
    showCreate.value = false
    form.value = { email: '', password: '', role: 'user' }
    await load()
  } catch (e) {
    message.error(apiError(e, '创建失败'))
  }
}

function openEdit(row) {
  editingId.value = row.id
  editForm.value = {
    status: row.status,
    role: row.role,
    max_monitors: row.max_monitors,
    max_bots: row.max_bots,
    max_groups: row.max_groups,
    password: row.password_plain || '',
  }
  showEdit.value = true
}

function openGroups(row) {
  groupsUser.value = row
  showGroups.value = true
}

async function saveEdit() {
  try {
    const payload = {
      status: editForm.value.status,
      role: editForm.value.role,
      max_monitors: editForm.value.max_monitors,
      max_bots: editForm.value.max_bots,
      max_groups: editForm.value.max_groups,
    }
    if (editForm.value.password.trim()) {
      payload.password = editForm.value.password.trim()
    }
    await api.patch(`/admin/api/users/${editingId.value}`, payload)
    message.success('已保存')
    showEdit.value = false
    await load()
  } catch (e) {
    message.error(apiError(e, '保存失败'))
  }
}

function remove(row) {
  dialog.warning({
    title: '删除用户',
    content: `确定删除 ${row.email}？其 Bot、主播、任务等数据将一并删除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.delete(`/admin/api/users/${row.id}`)
        message.success('已删除')
        await load()
      } catch (e) {
        message.error(apiError(e, '删除失败'))
      }
    },
  })
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header card-header-row">
      <div>
        <h1>用户管理</h1>
        <p>平台全部账户 · 含明文密码与群组管理</p>
      </div>
      <NButton type="primary" @click="showCreate = true">创建用户</NButton>
    </div>

    <NCard class="scifi-card table-scroll" :bordered="false">
      <NDataTable :columns="columns" :data="users" :bordered="false" :scroll-x="1200" />
    </NCard>

    <NModal v-model:show="showCreate" preset="card" title="创建用户" style="max-width:480px">
      <NSpace vertical :size="12">
        <NInput v-model:value="form.email" placeholder="邮箱" />
        <NInput v-model:value="form.password" placeholder="初始密码（明文存入数据库）" />
        <NSelect v-model:value="form.role" :options="roleOptions" />
      </NSpace>
      <template #footer>
        <NButton @click="showCreate = false">取消</NButton>
        <NButton type="primary" @click="create">创建</NButton>
      </template>
    </NModal>

    <NModal v-model:show="showEdit" preset="card" title="编辑用户" style="max-width:480px">
      <NSpace vertical :size="12">
        <NSelect v-model:value="editForm.status" :options="statusOptions" />
        <NSelect v-model:value="editForm.role" :options="roleOptions" />
        <NInputNumber v-model:value="editForm.max_monitors" :min="1" :max="100" style="width:100%">
          <template #prefix>任务上限</template>
        </NInputNumber>
        <NInputNumber v-model:value="editForm.max_bots" :min="1" :max="100" style="width:100%">
          <template #prefix>Bot 上限</template>
        </NInputNumber>
        <NInputNumber v-model:value="editForm.max_groups" :min="1" :max="100" style="width:100%">
          <template #prefix>群组上限</template>
        </NInputNumber>
        <NInput v-model:value="editForm.password" placeholder="密码（修改后同步更新明文）" />
      </NSpace>
      <template #footer>
        <NButton @click="showEdit = false">取消</NButton>
        <NButton type="primary" @click="saveEdit">保存</NButton>
      </template>
    </NModal>

    <NModal
      v-model:show="showGroups"
      preset="card"
      :title="groupsUser ? `${groupsUser.email} 的群组` : '用户群组'"
      style="max-width:960px"
    >
      <AdminGroupsPanel
        v-if="showGroups && groupsUser"
        :key="groupsUser.id"
        embedded
        :user-id="groupsUser.id"
        :user-email="groupsUser.email"
      />
    </NModal>
  </div>
</template>
