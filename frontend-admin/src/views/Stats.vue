<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { NGrid, NGi, NCard, NStatistic } from 'naive-ui'
import StatBarChart from '../components/StatBarChart.vue'
import RollingNumber from '../components/RollingNumber.vue'
import api from '../api'

const POLL_MS = 3000

const stats = ref({
  user_count: 0,
  active_task_count: 0,
  total_task_count: 0,
  follow_today: 0,
  follow_total: 0,
  join_today: 0,
  join_total: 0,
  sign_key_count: 0,
  bot_count: 0,
})

let pollTimer = null

const resourceChart = computed(() => [
  { label: '用户总数', value: stats.value.user_count, color: '#00f0ff' },
  { label: 'API Key', value: stats.value.sign_key_count, color: '#a855f7' },
  { label: '机器人', value: stats.value.bot_count, color: '#00ff9d' },
])

const taskChart = computed(() => [
  { label: '活跃任务', value: stats.value.active_task_count, color: '#00ff9d' },
  { label: '总任务', value: stats.value.total_task_count, color: '#00f0ff' },
])

const followChart = computed(() => [
  { label: '今日新关注', value: stats.value.follow_today, color: '#00ff9d' },
  { label: '总关注', value: stats.value.follow_total, color: '#00f0ff' },
])

const joinChart = computed(() => [
  { label: '今日进入', value: stats.value.join_today, color: '#a855f7' },
  { label: '总进入', value: stats.value.join_total, color: '#00f0ff' },
])

async function loadStats() {
  const { data } = await api.get('/admin/api/stats')
  stats.value = data
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(() => {
    loadStats().catch(() => {})
  }, POLL_MS)
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  await loadStats()
  startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div class="page-container">
    <div class="page-header card-header-row">
      <div>
        <h1>系统统计</h1>
        <p>全平台运行数据 · 每 {{ POLL_MS / 1000 }} 秒自动刷新</p>
      </div>
      <span class="live-badge">LIVE</span>
    </div>

    <NGrid :x-gap="16" :y-gap="16" :cols="3" responsive="screen" item-responsive class="summary-grid">
      <NGi span="3 s:1">
        <NCard class="scifi-card stat-card" :bordered="false">
          <NStatistic label="用户总数">
            <template #default>
              <RollingNumber :value="stats.user_count" size="md" />
            </template>
          </NStatistic>
        </NCard>
      </NGi>
      <NGi span="3 s:1">
        <NCard class="scifi-card stat-card" :bordered="false">
          <NStatistic label="监控任务">
            <template #default>
              <span class="ratio-value">
                <RollingNumber :value="stats.active_task_count" size="md" />
                <span class="ratio-sep">/</span>
                <RollingNumber :value="stats.total_task_count" size="md" />
              </span>
            </template>
          </NStatistic>
        </NCard>
      </NGi>
      <NGi span="3 s:1">
        <NCard class="scifi-card stat-card" :bordered="false">
          <NStatistic label="新关注">
            <template #default>
              <span class="ratio-value">
                <RollingNumber :value="stats.follow_today" size="md" />
                <span class="ratio-sep">/</span>
                <RollingNumber :value="stats.follow_total" size="md" />
              </span>
            </template>
          </NStatistic>
        </NCard>
      </NGi>
      <NGi span="3 s:1">
        <NCard class="scifi-card stat-card" :bordered="false">
          <NStatistic label="进入直播间">
            <template #default>
              <span class="ratio-value">
                <RollingNumber :value="stats.join_today" size="md" />
                <span class="ratio-sep">/</span>
                <RollingNumber :value="stats.join_total" size="md" />
              </span>
            </template>
          </NStatistic>
        </NCard>
      </NGi>
      <NGi span="3 s:1">
        <NCard class="scifi-card stat-card" :bordered="false">
          <NStatistic label="API Key 总数">
            <template #default>
              <RollingNumber :value="stats.sign_key_count" size="md" />
            </template>
          </NStatistic>
        </NCard>
      </NGi>
      <NGi span="3 s:1">
        <NCard class="scifi-card stat-card" :bordered="false">
          <NStatistic label="机器人总数">
            <template #default>
              <RollingNumber :value="stats.bot_count" size="md" />
            </template>
          </NStatistic>
        </NCard>
      </NGi>
    </NGrid>

    <NGrid :x-gap="16" :y-gap="16" :cols="2" responsive="screen" item-responsive class="chart-grid">
      <NGi span="2 m:1">
        <NCard class="scifi-card chart-card" :bordered="false">
          <StatBarChart title="平台资源" :items="resourceChart" />
        </NCard>
      </NGi>
      <NGi span="2 m:1">
        <NCard class="scifi-card chart-card" :bordered="false">
          <StatBarChart title="监控任务" :items="taskChart" />
        </NCard>
      </NGi>
      <NGi span="2 m:1">
        <NCard class="scifi-card chart-card" :bordered="false">
          <StatBarChart title="新关注事件" :items="followChart" />
        </NCard>
      </NGi>
      <NGi span="2 m:1">
        <NCard class="scifi-card chart-card" :bordered="false">
          <StatBarChart title="进入直播间" :items="joinChart" />
        </NCard>
      </NGi>
    </NGrid>
  </div>
</template>

<style scoped>
.summary-grid {
  margin-bottom: 16px;
}

.ratio-value {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}

.ratio-sep {
  font-family: var(--font-display);
  font-size: 1.1rem;
  color: #64748b;
}

.live-badge {
  font-family: var(--font-display);
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  color: #00ff9d;
  border: 1px solid rgba(0, 255, 157, 0.45);
  padding: 4px 10px;
  border-radius: 999px;
  box-shadow: 0 0 12px rgba(0, 255, 157, 0.25);
  animation: pulse-live 2s ease-in-out infinite;
}

@keyframes pulse-live {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

.stat-card :deep(.n-statistic-value) {
  margin-top: 4px;
}

.chart-grid {
  margin-top: 8px;
}

.chart-card {
  padding: 8px 4px 4px;
  min-height: 300px;
}

.chart-card :deep(.n-card__content) {
  padding: 16px 20px 12px;
}
</style>
