<script setup>
import { computed, h, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  NCard, NSelect, NTabs, NTabPane, NDataTable, NGrid, NGi, NSpace, NButton,
  useMessage,
} from 'naive-ui'
import api from '../api'
import { apiError } from '../apiError'
import RollingNumber from '../components/RollingNumber.vue'

const STATS_POLL_MS = 3000

const message = useMessage()
const tab = ref('follows')
const follows = ref([])
const joins = ref([])
const streamerFilter = ref('')
const timeFilter = ref('today')
const loading = ref(false)
const exporting = ref(false)
const stats = ref({ follow_today: 0, join_today: 0 })

const streamerOptions = ref([{ label: '全部主播', value: '' }])
const timeOptions = [
  { label: '今天', value: 'today' },
  { label: '全部', value: 'all' },
]

const followPage = ref(1)
const followPageSize = ref(50)
const followTotal = ref(0)

const joinPage = ref(1)
const joinPageSize = ref(50)
const joinTotal = ref(0)

let statsTimer = null
let prevFollowToday = 0
let prevJoinToday = 0

function tiktokUrl(uniqueId) {
  const uid = String(uniqueId || '').replace(/^@/, '')
  return uid ? `https://www.tiktok.com/@${uid}` : ''
}

function linkCell(url, label) {
  if (!url) return label || '-'
  return h(
    'a',
    { href: url, target: '_blank', rel: 'noopener noreferrer', class: 'profile-link' },
    label || url
  )
}

const followColumns = [
  {
    title: '主播',
    key: 'streamer_unique_id',
    render: (row) => linkCell(tiktokUrl(row.streamer_unique_id), `@${row.streamer_unique_id}`),
  },
  {
    title: '关注者',
    key: 'follower_unique_id',
    render: (row) => linkCell(tiktokUrl(row.follower_unique_id), `@${row.follower_unique_id}`),
  },
  { title: '昵称', key: 'follower_nickname' },
  {
    title: '客户首页链接',
    key: 'profile_url',
    ellipsis: { tooltip: true },
    render: (row) => linkCell(tiktokUrl(row.follower_unique_id), tiktokUrl(row.follower_unique_id)),
  },
  { title: '时间', key: 'detected_at', width: 180 },
]

const joinColumns = [
  {
    title: '主播',
    key: 'streamer_unique_id',
    render: (row) => linkCell(tiktokUrl(row.streamer_unique_id), `@${row.streamer_unique_id}`),
  },
  {
    title: '用户',
    key: 'guest_unique_id',
    render: (row) => linkCell(tiktokUrl(row.guest_unique_id), `@${row.guest_unique_id}`),
  },
  { title: '昵称', key: 'guest_nickname' },
  {
    title: '客户首页链接',
    key: 'profile_url',
    ellipsis: { tooltip: true },
    render: (row) => linkCell(tiktokUrl(row.guest_unique_id), tiktokUrl(row.guest_unique_id)),
  },
  { title: '时间', key: 'detected_at', width: 180 },
]

const followPagination = computed(() => ({
  page: followPage.value,
  pageSize: followPageSize.value,
  itemCount: followTotal.value,
  showSizePicker: true,
  pageSizes: [50, 100, 200],
  showQuickJumper: true,
  prefix: ({ itemCount }) => `共 ${itemCount} 条`,
}))

const joinPagination = computed(() => ({
  page: joinPage.value,
  pageSize: joinPageSize.value,
  itemCount: joinTotal.value,
  showSizePicker: true,
  pageSizes: [50, 100, 200],
  showQuickJumper: true,
  prefix: ({ itemCount }) => `共 ${itemCount} 条`,
}))

function filterParams() {
  const params = {}
  if (streamerFilter.value) params.streamer_unique_id = streamerFilter.value
  if (timeFilter.value === 'today') params.today_only = true
  return params
}

function listParams(page, pageSize) {
  return { ...filterParams(), page, page_size: pageSize }
}

async function loadStats() {
  const { data } = await api.get('/api/events/stats', { params: filterParams() })
  const followChanged = data.follow_today !== prevFollowToday
  const joinChanged = data.join_today !== prevJoinToday
  stats.value = data
  prevFollowToday = data.follow_today
  prevJoinToday = data.join_today

  if (followChanged && shouldRefreshList('follows')) {
    await loadFollows()
  }
  if (joinChanged && shouldRefreshList('joins')) {
    await loadJoins()
  }
}

function shouldRefreshList(kind) {
  if (timeFilter.value !== 'today') return false
  if (kind === 'follows') return followPage.value === 1
  return joinPage.value === 1
}

async function loadFollows() {
  const { data } = await api.get('/api/events/follows', {
    params: listParams(followPage.value, followPageSize.value),
  })
  follows.value = data.items
  followTotal.value = data.total
}

async function loadJoins() {
  const { data } = await api.get('/api/events/joins', {
    params: listParams(joinPage.value, joinPageSize.value),
  })
  joins.value = data.items
  joinTotal.value = data.total
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadStats(), loadFollows(), loadJoins()])
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  followPage.value = 1
  joinPage.value = 1
  loadAll()
}

function startStatsPolling() {
  stopStatsPolling()
  statsTimer = window.setInterval(() => {
    loadStats().catch(() => {})
  }, STATS_POLL_MS)
}

function stopStatsPolling() {
  if (statsTimer) {
    window.clearInterval(statsTimer)
    statsTimer = null
  }
}

function onFollowPageChange(page) {
  followPage.value = page
  loadFollows()
}

function onFollowPageSizeChange(pageSize) {
  followPageSize.value = pageSize
  followPage.value = 1
  loadFollows()
}

function onJoinPageChange(page) {
  joinPage.value = page
  loadJoins()
}

function onJoinPageSizeChange(pageSize) {
  joinPageSize.value = pageSize
  joinPage.value = 1
  loadJoins()
}

function parseFilename(disposition) {
  const match = disposition?.match(/filename="?([^";]+)"?/)
  return match?.[1] || 'export'
}

async function exportCurrent(format) {
  const kind = tab.value
  exporting.value = true
  try {
    const res = await api.get(`/api/events/${kind}/export`, {
      params: { ...filterParams(), format },
      responseType: 'blob',
    })
    const filename = parseFilename(res.headers['content-disposition'])
    const blob = new Blob([res.data], {
      type: format === 'csv' ? 'text/csv;charset=utf-8' : 'text/plain;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = decodeURIComponent(filename)
    anchor.click()
    URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch (e) {
    message.error(apiError(e, '导出失败'))
  } finally {
    exporting.value = false
  }
}

watch(tab, () => {
  if (tab.value === 'follows' && !follows.value.length && followTotal.value === 0) {
    loadFollows()
  }
  if (tab.value === 'joins' && !joins.value.length && joinTotal.value === 0) {
    loadJoins()
  }
})

onMounted(async () => {
  const { data } = await api.get('/api/streamers')
  streamerOptions.value = [
    { label: '全部主播', value: '' },
    ...data.map((s) => ({ label: `@${s.unique_id}`, value: s.unique_id })),
  ]
  await loadAll()
  prevFollowToday = stats.value.follow_today
  prevJoinToday = stats.value.join_today
  startStatsPolling()
})

onUnmounted(() => {
  stopStatsPolling()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1>事件流水</h1>
      <p>新关注与进房记录</p>
    </div>

    <NGrid :x-gap="16" :y-gap="16" :cols="2" responsive="screen" item-responsive style="margin-bottom: 16px">
      <NGi span="2 m:1">
        <NCard class="scifi-card stat-card" :bordered="false">
          <div class="stat-label">今日新关注</div>
          <RollingNumber :value="stats.follow_today" suffix="人" />
        </NCard>
      </NGi>
      <NGi span="2 m:1">
        <NCard class="scifi-card stat-card" :bordered="false">
          <div class="stat-label">今日新进直播间</div>
          <RollingNumber :value="stats.join_today" suffix="人" />
        </NCard>
      </NGi>
    </NGrid>

    <NCard class="scifi-card table-scroll" :bordered="false">
      <NTabs v-model:value="tab" type="line" animated class="events-tabs">
        <template #suffix>
          <NSpace :size="8" align="center" class="filter-row">
            <NSelect
              v-model:value="streamerFilter"
              :options="streamerOptions"
              size="small"
              class="streamer-filter"
              @update:value="onFilterChange"
            />
            <NSelect
              v-model:value="timeFilter"
              :options="timeOptions"
              size="small"
              class="time-filter"
              @update:value="onFilterChange"
            />
            <NButton size="small" :loading="exporting" @click="exportCurrent('txt')">导出 TXT</NButton>
            <NButton size="small" :loading="exporting" @click="exportCurrent('csv')">导出表格</NButton>
          </NSpace>
        </template>
        <NTabPane name="follows" tab="新关注">
          <NDataTable
            remote
            :loading="loading"
            :columns="followColumns"
            :data="follows"
            :bordered="false"
            :pagination="followPagination"
            :scroll-x="1100"
            @update:page="onFollowPageChange"
            @update:page-size="onFollowPageSizeChange"
          />
        </NTabPane>
        <NTabPane name="joins" tab="新进直播间">
          <NDataTable
            remote
            :loading="loading"
            :columns="joinColumns"
            :data="joins"
            :bordered="false"
            :pagination="joinPagination"
            :scroll-x="1100"
            @update:page="onJoinPageChange"
            @update:page-size="onJoinPageSizeChange"
          />
        </NTabPane>
      </NTabs>
    </NCard>
  </div>
</template>

<style scoped>
.stat-card {
  min-height: 96px;
}

.stat-label {
  font-size: 14px;
  color: #94a3b8;
  margin-bottom: 10px;
}

.events-tabs :deep(.n-tabs-nav) {
  display: flex;
  align-items: center;
}

.events-tabs :deep(.n-tabs-nav-scroll-wrapper) {
  flex: 1;
  min-width: 0;
}

.events-tabs :deep(.n-tabs-nav__suffix) {
  flex-shrink: 0;
  padding-left: 16px;
  margin-bottom: 1px;
}

.filter-row {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.streamer-filter {
  width: 160px;
}

.time-filter {
  width: 90px;
}

:deep(.profile-link) {
  color: #00f0ff;
  text-decoration: none;
  word-break: break-all;
}

:deep(.profile-link:hover) {
  text-decoration: underline;
}
</style>
