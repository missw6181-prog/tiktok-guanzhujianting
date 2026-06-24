<script setup>
import { computed, h, inject, onMounted, ref } from 'vue'
import {
  useMessage, NCard, NButton, NDataTable, NModal, NSpace, NSelect, NAlert, NEmpty,
} from 'naive-ui'
import api from '../api'
import { apiError } from '../apiError'

const me = inject('me')
const reloadMe = inject('reloadMe')
const message = useMessage()
const list = ref([])
const bots = ref([])
const show = ref(false)
const selectedBotId = ref(null)
const discovered = ref([])
const discoveredLoaded = ref(false)
const discovering = ref(false)
const importing = ref(false)
const refreshing = ref(false)
const checkedRowKeys = ref([])

const uniqueGroupCount = computed(() => new Set(list.value.map((g) => g.chat_id)).size)

const botOptions = computed(() =>
  bots.value.map((b) => ({
    label: `${b.name} (${b.bot_telegram_id || b.id})`,
    value: b.id,
  }))
)

const columns = [
  { title: '名称', key: 'name' },
  {
    title: '所属机器人',
    key: 'bot_id',
    width: 140,
    render: (row) => botName(row.bot_id),
  },
  { title: 'Chat ID', key: 'chat_id', minWidth: 160 },
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

const discoverColumns = [
  { type: 'selection' },
  { title: '群名称', key: 'name' },
  { title: 'Chat ID', key: 'chat_id', minWidth: 160 },
  { title: '类型', key: 'chat_type', width: 100 },
]

async function load() {
  try {
    const [groupsRes, botsRes] = await Promise.all([
      api.get('/api/groups'),
      api.get('/api/bots'),
    ])
    list.value = groupsRes.data
    bots.value = botsRes.data
  } catch (e) {
    message.error(apiError(e, '加载失败'))
  }
}

function botName(botId) {
  if (!botId) return '-'
  const bot = bots.value.find((b) => b.id === botId)
  return bot ? bot.name : `#${botId}`
}

function openDialog() {
  selectedBotId.value = bots.value[0]?.id ?? null
  discovered.value = []
  discoveredLoaded.value = false
  checkedRowKeys.value = []
  show.value = true
}

async function discover() {
  if (!selectedBotId.value) return
  discovering.value = true
  discoveredLoaded.value = false
  checkedRowKeys.value = []
  try {
    const { data } = await api.get(`/api/bots/${selectedBotId.value}/discover-groups`)
    discovered.value = data
    discoveredLoaded.value = true
    if (!data.length) {
      message.info('未发现新群组，请确认 Bot 已在群内并有消息记录')
    }
  } catch (e) {
    message.error(apiError(e, '获取失败'))
  } finally {
    discovering.value = false
  }
}

async function refreshNames() {
  refreshing.value = true
  try {
    const { data } = await api.post('/api/groups/refresh-names')
    await load()
    if (data.failed?.length) {
      message.warning(`已更新 ${data.updated} 个，未变化 ${data.unchanged} 个，失败 ${data.failed.length} 个`)
    } else if (data.updated > 0) {
      message.success(`已更新 ${data.updated} 个群组名称`)
    } else {
      message.info('群组名称已是最新')
    }
  } catch (e) {
    message.error(apiError(e, '刷新失败'))
  } finally {
    refreshing.value = false
  }
}

async function importSelected() {
  const rows = discovered.value.filter((r) => checkedRowKeys.value.includes(r.chat_id))
  if (!rows.length) return
  importing.value = true
  try {
    const { data } = await api.post('/api/groups/batch-import', {
      bot_id: selectedBotId.value,
      items: rows.map((row) => ({ chat_id: row.chat_id, name: row.name })),
    })
    message.success(`已导入 ${data.imported} 个群组${data.skipped ? `，跳过 ${data.skipped} 个` : ''}`)
    show.value = false
    await load()
    await reloadMe()
  } catch (e) {
    message.error(apiError(e, '导入失败'))
  } finally {
    importing.value = false
  }
}

async function remove(id) {
  try {
    await api.delete(`/api/groups/${id}`)
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
        <h1>群组</h1>
        <p>
          群组 {{ uniqueGroupCount }}/{{ me?.max_groups || 10 }}
          <span v-if="list.length > uniqueGroupCount" class="sub">（{{ list.length }} 条 Bot 绑定）</span>
        </p>
      </div>
      <NSpace>
        <NButton :loading="refreshing" @click="refreshNames">刷新群组名称</NButton>
        <NButton type="primary" @click="openDialog">从机器人获取群组</NButton>
      </NSpace>
    </div>

    <NCard class="scifi-card table-scroll" :bordered="false">
      <NDataTable :columns="columns" :data="list" :bordered="false" :scroll-x="800" />
    </NCard>

    <NModal v-model:show="show" preset="card" title="从机器人获取群组" style="max-width:640px">
      <NAlert
        type="info"
        :show-icon="true"
        title="说明"
        style="margin-bottom: 16px"
      >
        Telegram 不提供「Bot 全部群组」列表。只能发现 Bot 已收到消息、或被拉入群后的会话。请先把 Bot 加入目标群，并在群里发一条消息后再获取。
      </NAlert>
      <NSpace vertical :size="12">
        <NSelect
          v-model:value="selectedBotId"
          :options="botOptions"
          placeholder="请选择机器人"
        />
        <NButton :loading="discovering" :disabled="!selectedBotId" @click="discover">
          获取群组列表
        </NButton>
        <NDataTable
          v-if="discovered.length"
          v-model:checked-row-keys="checkedRowKeys"
          :row-key="(row) => row.chat_id"
          :columns="discoverColumns"
          :data="discovered"
          :bordered="false"
        />
        <NEmpty v-else-if="discoveredLoaded" description="未发现可导入的群组" />
      </NSpace>
      <template #footer>
        <NButton @click="show = false">取消</NButton>
        <NButton
          type="primary"
          :loading="importing"
          :disabled="!checkedRowKeys.length"
          @click="importSelected"
        >
          导入选中 ({{ checkedRowKeys.length }})
        </NButton>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.sub { font-size: 12px; color: #94a3b8; }
</style>
