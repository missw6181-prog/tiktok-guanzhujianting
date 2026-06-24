<script setup>
import { computed, h, inject, onMounted, onUnmounted, ref } from 'vue'
import {
  useMessage, NCard, NButton, NDataTable, NModal, NSpace, NTag, NTooltip, NSwitch,
  NForm, NFormItem, NInput, NSelect, NRadioGroup, NRadio, NDivider,
} from 'naive-ui'
import api from '../api'
import { apiError } from '../apiError'

const me = inject('me')
const reloadMe = inject('reloadMe')
const message = useMessage()
const tasks = ref([])
const bots = ref([])
const groups = ref([])
const streamers = ref([])
const poolKeys = ref([])
const show = ref(false)
const editingId = ref(null)
const form = ref({
  unique_id: '',
  key_mode: 'pool',
  sign_api_key_id: null,
  sign_api_key: '',
  follow_bot_id: null,
  follow_group_id: null,
})

const poolOptions = computed(() => {
  const keys = editingId.value
    ? poolKeys.value.filter((k) => !k.in_use || k.id === form.value.sign_api_key_id)
    : poolKeys.value.filter((k) => !k.in_use)
  return keys.map((k) => ({
    label: keyOptionLabel(k),
    value: k.id,
  }))
})

const botsInPushUse = computed(() => {
  const used = new Set()
  for (const task of tasks.value) {
    if (!task.enabled || !task.follow_bot_id) continue
    if (editingId.value && task.id === editingId.value) continue
    used.add(task.follow_bot_id)
  }
  return used
})

const botOptions = computed(() =>
  bots.value.map((b) => {
    const busy = botsInPushUse.value.has(b.id)
    return {
      label: busy ? `${b.name}（推送占用中）` : b.name,
      value: b.id,
      disabled: busy,
    }
  })
)

const availableBotCount = computed(() =>
  botOptions.value.filter((o) => !o.disabled).length
)

const filteredGroups = computed(() => {
  if (!form.value.follow_bot_id) return []
  return groups.value
    .filter((g) => g.bot_id === form.value.follow_bot_id)
    .map((g) => ({ label: `${g.name} (${g.chat_id})`, value: g.id }))
})

function statusType(s) {
  return {
    live: 'success',
    offline: 'default',
    error: 'error',
    connecting: 'warning',
    retrying: 'warning',
    rate_limited: 'error',
    idle: 'default',
  }[s] || 'default'
}

function statusLabel(s, enabled = true) {
  if (s === 'idle') return enabled ? '空闲' : '已停用'
  return {
    live: '直播中',
    offline: '未开播',
    error: '异常',
    connecting: '连接中',
    retrying: '重试中',
    rate_limited: '限流',
  }[s] || s
}

function botLabel(id) {
  const bot = bots.value.find((b) => b.id === id)
  return bot ? bot.name : '-'
}

function groupLabel(id) {
  const group = groups.value.find((g) => g.id === id)
  return group ? group.name : '-'
}

function keyOptionLabel(k) {
  const name = k.label || `Key #${k.id}`
  const tail = k.sign_api_key ? k.sign_api_key.slice(-10) : ''
  const remain = k.rate_limits?.daily_remaining != null
    ? `剩余 ${k.rate_limits.daily_remaining} 次`
    : '配额未查询'
  return `${name} · …${tail} · ${remain}`
}

const selectedPoolKey = computed(() =>
  poolKeys.value.find((k) => k.id === form.value.sign_api_key_id)
)

function resetForm() {
  form.value = {
    unique_id: '',
    key_mode: 'pool',
    sign_api_key_id: null,
    sign_api_key: '',
    follow_bot_id: null,
    follow_group_id: null,
  }
}

async function loadPoolKeys() {
  const { data } = await api.get('/api/sign-keys')
  poolKeys.value = data
}

async function loadTasks() {
  const { data } = await api.get('/api/tasks')
  tasks.value = data
}

async function loadAll() {
  try {
    const [t, b, g, s] = await Promise.all([
      api.get('/api/tasks'),
      api.get('/api/bots'),
      api.get('/api/groups'),
      api.get('/api/streamers'),
    ])
    tasks.value = t.data
    bots.value = b.data
    groups.value = g.data
    streamers.value = s.data
  } catch (e) {
    message.error(apiError(e, '加载失败'))
  }
}

function openCreate() {
  editingId.value = null
  resetForm()
  loadPoolKeys()
  show.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = {
    unique_id: row.streamer.unique_id,
    key_mode: 'pool',
    sign_api_key_id: row.sign_api_key_id,
    sign_api_key: row.sign_api_key || '',
    follow_bot_id: row.follow_bot_id,
    follow_group_id: row.follow_group_id,
  }
  loadPoolKeys()
  show.value = true
}

function onBotChange() {
  if (botsInPushUse.value.has(form.value.follow_bot_id)) {
    form.value.follow_bot_id = null
    form.value.follow_group_id = null
    return
  }
  const allowed = groups.value.some(
    (g) => g.bot_id === form.value.follow_bot_id && g.id === form.value.follow_group_id
  )
  if (!allowed) form.value.follow_group_id = null
}

function buildKeyPayload() {
  if (form.value.key_mode === 'pool') {
    if (!form.value.sign_api_key_id) {
      message.warning('请选择 API Key')
      return null
    }
    return { sign_api_key_id: form.value.sign_api_key_id }
  }
  if (!form.value.sign_api_key.trim()) {
    message.warning('请填写 API Key')
    return null
  }
  return { sign_api_key: form.value.sign_api_key.trim() }
}

async function save() {
  if (!form.value.follow_bot_id || !form.value.follow_group_id) {
    message.warning('请选择机器人和群组')
    return
  }
  const keyPayload = buildKeyPayload()
  if (!keyPayload) return

  try {
    if (editingId.value) {
      await api.patch(`/api/tasks/${editingId.value}`, {
        ...keyPayload,
        follow_bot_id: form.value.follow_bot_id,
        follow_group_id: form.value.follow_group_id,
      })
      message.success('任务已更新')
    } else {
      if (!form.value.unique_id.trim()) {
        message.warning('请填写主播 ID')
        return
      }
      let streamer = streamers.value.find(
        (s) => s.unique_id === form.value.unique_id.trim().replace(/^@/, '')
      )
      if (!streamer) {
        const { data } = await api.post('/api/streamers', { unique_id: form.value.unique_id })
        streamer = data
      }
      await api.post('/api/tasks', {
        streamer_id: streamer.id,
        ...keyPayload,
        follow_bot_id: form.value.follow_bot_id,
        follow_group_id: form.value.follow_group_id,
        enabled: true,
      })
      message.success('任务已创建')
    }
    show.value = false
    editingId.value = null
    await loadAll()
    await reloadMe()
  } catch (e) {
    message.error(apiError(e, '保存失败'))
  }
}

async function toggle(row, enabled) {
  const prev = row.enabled
  row.enabled = enabled
  try {
    await api.patch(`/api/tasks/${row.id}`, { enabled })
    message.success('已更新')
  } catch {
    row.enabled = prev
  }
}

async function remove(id) {
  try {
    await api.delete(`/api/tasks/${id}`)
    message.success('已删除')
    await loadAll()
    await reloadMe()
  } catch (e) {
    message.error(apiError(e, '删除失败'))
  }
}

const columns = [
  {
    title: '主播',
    key: 'streamer',
    render: (row) => `@${row.streamer.unique_id}`,
  },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render: (row) => {
      const tag = h(
        NTag,
        { type: statusType(row.status), bordered: false },
        { default: () => statusLabel(row.status, row.enabled) }
      )
      if (!row.last_error) return tag
      return h(NTooltip, { placement: 'top' }, {
        trigger: () => tag,
        default: () => row.last_error,
      })
    },
  },
  {
    title: 'API Key',
    key: 'sign_api_key',
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'mono-text' }, row.sign_api_key || '未配置'),
  },
  {
    title: '新关注推送',
    key: 'push',
    render: (row) => `${botLabel(row.follow_bot_id)} → ${groupLabel(row.follow_group_id)}`,
  },
  {
    title: '启用',
    key: 'enabled',
    width: 80,
    render: (row) => h(NSwitch, {
      value: row.enabled,
      onUpdateValue: (v) => toggle(row, v),
    }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 140,
    render: (row) => h(NSpace, null, {
      default: () => [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => remove(row.id) }, { default: () => '删除' }),
      ],
    }),
  },
]

const POLL_MS = 3000
let pollTimer = null

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(() => {
    loadTasks().catch(() => {})
  }, POLL_MS)
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  loadAll()
  startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div class="page-container">
    <div class="page-header card-header-row">
      <div>
        <h1>监控任务</h1>
        <p>{{ tasks.length }}/{{ me?.max_monitors || 10 }} 个任务</p>
      </div>
      <NButton type="primary" @click="openCreate">新建任务</NButton>
    </div>

    <NCard class="scifi-card table-scroll" :bordered="false">
      <NDataTable :columns="columns" :data="tasks" :bordered="false" :scroll-x="1100" />
    </NCard>

    <NModal
      v-model:show="show"
      preset="card"
      :title="editingId ? '编辑监控任务' : '新建监控任务'"
      class="task-modal"
      style="max-width: 600px"
    >
      <NForm label-placement="top" :show-feedback="false" class="task-form">
        <NFormItem label="主播 ID">
          <NInput
            v-model:value="form.unique_id"
            :disabled="!!editingId"
            placeholder="不含 @，如 somecreator"
          />
        </NFormItem>

        <div class="key-section scifi-card">
          <div class="key-section-head">
            <span class="key-section-title">API Key</span>
            <span class="key-section-sub">每个 Key 全局只能绑定一个监控任务</span>
          </div>

          <NFormItem label="绑定方式" class="key-form-item">
            <NRadioGroup v-model:value="form.key_mode" class="key-mode-group">
              <NSpace vertical :size="10">
                <NRadio value="pool">从 Key 池选择已有 Key</NRadio>
                <NRadio value="new">粘贴新的 Key（自动加入 Key 池）</NRadio>
              </NSpace>
            </NRadioGroup>
          </NFormItem>

          <NFormItem
            v-if="form.key_mode === 'pool'"
            label="选择 Key"
            class="key-form-item"
          >
            <NSelect
              v-model:value="form.sign_api_key_id"
              :options="poolOptions"
              placeholder="请选择空闲 API Key"
              filterable
              clearable
              consistent-menu-width
              :menu-props="{ style: { maxWidth: '520px' } }"
            />
            <div v-if="selectedPoolKey" class="key-preview">
              <div class="key-preview-label">已选 Key</div>
              <div class="key-preview-value mono-text">{{ selectedPoolKey.sign_api_key }}</div>
              <div v-if="selectedPoolKey.rate_limits?.daily_remaining != null" class="key-preview-quota">
                今日剩余 {{ selectedPoolKey.rate_limits.daily_remaining }} 次
              </div>
            </div>
            <div v-else-if="!poolOptions.length" class="hint-text">
              Key 池暂无空闲 Key，请先到「API Key 池」添加，或切换为粘贴新 Key。
            </div>
          </NFormItem>

          <NFormItem
            v-else
            label="粘贴 Key"
            class="key-form-item"
          >
            <NInput
              v-model:value="form.sign_api_key"
              type="textarea"
              :rows="3"
              placeholder="粘贴 Euler 监控 API Key"
            />
          </NFormItem>

          <div class="hint-text key-hint">
            可先前往「API Key 池」批量添加；创建任务时会占用所选 Key。
          </div>
        </div>

        <NDivider>新关注推送</NDivider>
        <NFormItem label="机器人">
          <NSelect
            v-model:value="form.follow_bot_id"
            :options="botOptions"
            placeholder="请选择机器人"
            @update:value="onBotChange"
          />
          <div v-if="!editingId && bots.length && !availableBotCount" class="hint-text">
            所有机器人均已被启用的监控任务占用，请先停用其他任务或添加新机器人。
          </div>
          <div v-else-if="botsInPushUse.size" class="hint-text">
            标注「推送占用中」的机器人已被其他启用任务使用，不可重复选择。
          </div>
        </NFormItem>
        <NFormItem label="群组">
          <NSelect
            v-model:value="form.follow_group_id"
            :options="filteredGroups"
            :disabled="!form.follow_bot_id"
            placeholder="请先选择机器人"
          />
          <div v-if="form.follow_bot_id && !filteredGroups.length" class="hint-text">
            该机器人下暂无群组，请先在「群组」页从该机器人导入
          </div>
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton @click="show = false">取消</NButton>
        <NButton type="primary" @click="save">{{ editingId ? '保存' : '创建' }}</NButton>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.task-form :deep(.n-form-item) {
  margin-bottom: 18px;
}

.key-section {
  padding: 16px 16px 12px;
  margin-bottom: 8px;
}

.key-section-head {
  margin-bottom: 14px;
}

.key-section-title {
  display: block;
  font-family: var(--font-display);
  font-size: 0.78rem;
  letter-spacing: 0.1em;
  color: var(--scifi-cyan);
  text-transform: uppercase;
}

.key-section-sub {
  display: block;
  margin-top: 4px;
  font-size: 0.82rem;
  color: #64748b;
}

.key-form-item {
  margin-bottom: 14px !important;
}

.key-form-item:last-of-type {
  margin-bottom: 8px !important;
}

.key-mode-group {
  width: 100%;
}

.key-preview {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 240, 255, 0.18);
  border-radius: 4px;
  background: rgba(0, 240, 255, 0.04);
}

.key-preview-label {
  font-size: 0.75rem;
  color: #64748b;
  margin-bottom: 6px;
}

.key-preview-value {
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
  color: #cbd5e1;
}

.key-preview-quota {
  margin-top: 6px;
  font-size: 0.82rem;
  color: var(--scifi-green);
}

.key-hint {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 240, 255, 0.08);
}
</style>
