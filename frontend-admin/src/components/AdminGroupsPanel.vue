<script setup>
import { computed, h, onMounted, ref, watch } from 'vue'
import {
  useMessage, useDialog, NButton, NDataTable, NInput, NModal, NSpace, NTag, NSelect, NSwitch,
} from 'naive-ui'
import api from '../api'
import { apiError } from '../apiError'

const props = defineProps({
  userId: { type: Number, default: null },
  userEmail: { type: String, default: '' },
  embedded: { type: Boolean, default: false },
})

const message = useMessage()
const dialog = useDialog()
const list = ref([])
const userOptions = ref([])
const botOptions = ref([])
const showCreate = ref(false)
const showEdit = ref(false)
const editingId = ref(null)
const form = ref({ user_id: null, bot_id: null, name: '', chat_id: '', is_active: true })
const editForm = ref({ user_id: null, bot_id: null, name: '', chat_id: '', is_active: true })

const userSelectOptions = computed(() =>
  userOptions.value.map((u) => ({
    label: `${u.email} (#${u.id})`,
    value: u.id,
    disabled: u.status !== 'active',
  }))
)

const botSelectOptions = computed(() =>
  botOptions.value.map((b) => ({
    label: `${b.name} (#${b.id})`,
    value: b.id,
  }))
)

const columns = computed(() => {
  const cols = [
    { title: 'ID', key: 'id', width: 60 },
  ]
  if (!props.userId) {
    cols.push({ title: '所属用户', key: 'user_email', minWidth: 160 })
  }
  cols.push(
    { title: '群名称', key: 'name', minWidth: 120 },
    {
      title: 'Chat ID',
      key: 'chat_id',
      minWidth: 140,
      render: (row) => h('span', { class: 'mono-text' }, row.chat_id),
    },
    {
      title: '绑定 Bot',
      key: 'bot_name',
      width: 140,
      render: (row) => row.bot_name || '-',
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
  )
  return cols
})

async function loadUsers() {
  const { data } = await api.get('/admin/api/user-options')
  userOptions.value = data
}

async function loadBots(userId) {
  if (!userId) {
    botOptions.value = []
    return
  }
  const { data } = await api.get('/admin/api/bots')
  botOptions.value = data.filter((b) => b.user_id === userId)
}

async function load() {
  try {
    const url = props.userId
      ? `/admin/api/users/${props.userId}/groups`
      : '/admin/api/groups'
    const { data } = await api.get(url)
    list.value = data
  } catch (e) {
    message.error(apiError(e, '加载群组失败'))
  }
}

async function loadAll() {
  if (!props.userId) {
    await loadUsers()
  }
  await load()
}

function defaultUserId() {
  return props.userId ?? userOptions.value.find((u) => u.status === 'active')?.id ?? null
}

function openCreateDialog() {
  const uid = defaultUserId()
  form.value = { user_id: uid, bot_id: null, name: '', chat_id: '', is_active: true }
  loadBots(uid)
  showCreate.value = true
}

async function create() {
  if (!form.value.user_id) {
    message.warning('请选择所属用户')
    return
  }
  if (!form.value.name.trim() || !form.value.chat_id.trim()) {
    message.warning('请填写群名称和 Chat ID')
    return
  }
  try {
    await api.post('/admin/api/groups', {
      user_id: form.value.user_id,
      bot_id: form.value.bot_id,
      name: form.value.name.trim(),
      chat_id: form.value.chat_id.trim(),
      is_active: form.value.is_active,
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
    bot_id: row.bot_id,
    name: row.name,
    chat_id: row.chat_id,
    is_active: row.is_active,
  }
  loadBots(row.user_id)
  showEdit.value = true
}

async function saveEdit() {
  try {
    await api.patch(`/admin/api/groups/${editingId.value}`, {
      user_id: editForm.value.user_id,
      bot_id: editForm.value.bot_id,
      name: editForm.value.name.trim(),
      chat_id: editForm.value.chat_id.trim(),
      is_active: editForm.value.is_active,
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
    title: '删除群组',
    content: `确定删除 ${row.name}（${row.chat_id}）？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.delete(`/admin/api/groups/${row.id}`)
        message.success('已删除')
        await load()
      } catch (e) {
        message.error(apiError(e, '删除失败'))
      }
    },
  })
}

watch(() => form.value.user_id, (uid) => {
  form.value.bot_id = null
  loadBots(uid)
})

watch(() => editForm.value.user_id, (uid) => {
  loadBots(uid)
})

watch(() => props.userId, () => {
  loadAll()
})

onMounted(loadAll)

defineExpose({ load })
</script>

<template>
  <div :class="{ 'embedded-panel': embedded }">
    <div v-if="!embedded" class="page-header card-header-row">
      <div>
        <h1>群组管理</h1>
        <p>全平台 {{ list.length }} 个群组</p>
      </div>
      <NButton type="primary" @click="openCreateDialog">添加群组</NButton>
    </div>
    <div v-else class="embedded-header">
      <p>{{ userEmail }} 的群组（{{ list.length }}）</p>
      <NButton size="small" type="primary" @click="openCreateDialog">添加群组</NButton>
    </div>

    <NDataTable :columns="columns" :data="list" :bordered="false" :scroll-x="1000" />

    <NModal v-model:show="showCreate" preset="card" title="添加群组" style="max-width:480px">
      <NSpace vertical :size="12">
        <NSelect
          v-if="!userId"
          v-model:value="form.user_id"
          :options="userSelectOptions"
          placeholder="所属用户"
        />
        <NSelect
          v-model:value="form.bot_id"
          :options="botSelectOptions"
          clearable
          placeholder="绑定 Bot（可选）"
        />
        <NInput v-model:value="form.name" placeholder="群名称" />
        <NInput v-model:value="form.chat_id" placeholder="Telegram Chat ID" />
        <div class="form-row">
          <span>启用</span>
          <NSwitch v-model:value="form.is_active" />
        </div>
      </NSpace>
      <template #footer>
        <NButton @click="showCreate = false">取消</NButton>
        <NButton type="primary" @click="create">添加</NButton>
      </template>
    </NModal>

    <NModal v-model:show="showEdit" preset="card" title="编辑群组" style="max-width:480px">
      <NSpace vertical :size="12">
        <NSelect
          v-if="!userId"
          v-model:value="editForm.user_id"
          :options="userSelectOptions"
          placeholder="所属用户"
        />
        <NSelect
          v-model:value="editForm.bot_id"
          :options="botSelectOptions"
          clearable
          placeholder="绑定 Bot（可选）"
        />
        <NInput v-model:value="editForm.name" placeholder="群名称" />
        <NInput v-model:value="editForm.chat_id" placeholder="Telegram Chat ID" />
        <div class="form-row">
          <span>启用</span>
          <NSwitch v-model:value="editForm.is_active" />
        </div>
      </NSpace>
      <template #footer>
        <NButton @click="showEdit = false">取消</NButton>
        <NButton type="primary" @click="saveEdit">保存</NButton>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.embedded-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
