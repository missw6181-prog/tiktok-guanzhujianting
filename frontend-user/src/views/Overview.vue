<script setup>
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import SciFiDashPanel from '../components/dashboard/SciFiDashPanel.vue'
import SciFiRingGauge from '../components/dashboard/SciFiRingGauge.vue'
import SciFiHeroMetric from '../components/dashboard/SciFiHeroMetric.vue'
import SciFiActivityTicker from '../components/dashboard/SciFiActivityTicker.vue'
import RollingNumber from '../components/RollingNumber.vue'
import api from '../api'

const POLL_MS = 3000
const POLL_SEC = POLL_MS / 1000
const HISTORY_LEN = 24

const me = inject('me', ref(null))

const stats = ref({
  active_task_count: 0,
  inactive_task_count: 0,
  total_task_count: 0,
  sign_key_in_use: 0,
  sign_key_idle: 0,
  sign_key_total: 0,
  bot_pushing: 0,
  bot_idle: 0,
  bot_total: 0,
  group_pushing: 0,
  group_idle: 0,
  group_total: 0,
  follow_today: 0,
  follow_total: 0,
  join_today: 0,
  join_total: 0,
})

const followHistory = ref([])
const joinHistory = ref([])
const deltas = ref({ follow_today: 0, join_today: 0 })
const flashKeys = ref(new Set())
const activityFeed = ref([])
const clock = ref('')
const pollCountdown = ref(POLL_SEC)
const ready = ref(false)

let pollTimer = null
let clockTimer = null
let countdownTimer = null
let activitySeq = 0

const resourceBars = computed(() => [
  {
    key: 'tasks',
    label: '监控任务',
    primary: stats.value.active_task_count,
    total: stats.value.total_task_count,
    primaryLabel: '监控中',
    idleLabel: '已停止',
    color: '#00ff9d',
  },
  {
    key: 'keys',
    label: 'API Key',
    primary: stats.value.sign_key_in_use,
    total: stats.value.sign_key_total,
    primaryLabel: '使用中',
    idleLabel: '未使用',
    color: '#a855f7',
  },
  {
    key: 'bots',
    label: '机器人',
    primary: stats.value.bot_pushing,
    total: stats.value.bot_total,
    primaryLabel: '推送中',
    idleLabel: '闲置',
    color: '#00f0ff',
  },
  {
    key: 'groups',
    label: '群组',
    primary: stats.value.group_pushing,
    total: stats.value.group_total,
    primaryLabel: '推送中',
    idleLabel: '闲置',
    color: '#00ff9d',
  },
])

function pushHistory(list, value) {
  return [...list.slice(-(HISTORY_LEN - 1)), value]
}

function flash(key, ms = 750) {
  flashKeys.value.add(key)
  flashKeys.value = new Set(flashKeys.value)
  window.setTimeout(() => {
    flashKeys.value.delete(key)
    flashKeys.value = new Set(flashKeys.value)
  }, ms)
}

function pushActivity(text) {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  const type = text.includes('新关注') ? 'follow' : 'join'
  activityFeed.value = [
    { id: ++activitySeq, text, time, type },
    ...activityFeed.value,
  ].slice(0, 8)
}

function applyStats(data) {
  const prev = stats.value
  const nextDeltas = { follow_today: 0, join_today: 0 }

  if (ready.value) {
    if (data.follow_today > prev.follow_today) {
      const d = data.follow_today - prev.follow_today
      nextDeltas.follow_today = d
      pushActivity(`新关注 +${d}`)
      flash('follow')
    }
    if (data.join_today > prev.join_today) {
      const d = data.join_today - prev.join_today
      nextDeltas.join_today = d
      pushActivity(`新进直播间 +${d}`)
      flash('join')
    }
    ;['active_task_count', 'sign_key_in_use', 'bot_pushing', 'group_pushing'].forEach((k) => {
      if (data[k] !== prev[k]) flash('resources')
    })
  }

  stats.value = data
  deltas.value = nextDeltas
  followHistory.value = pushHistory(followHistory.value, data.follow_today)
  joinHistory.value = pushHistory(joinHistory.value, data.join_today)
  ready.value = true
}

async function loadStats() {
  const { data } = await api.get('/api/dashboard/stats')
  applyStats(data)
  pollCountdown.value = POLL_SEC
}

function tickClock() {
  clock.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

function stopCountdown() {
  if (countdownTimer) {
    window.clearInterval(countdownTimer)
    countdownTimer = null
  }
}

function startCountdown() {
  stopCountdown()
  pollCountdown.value = POLL_SEC
  countdownTimer = window.setInterval(() => {
    pollCountdown.value -= 1
    if (pollCountdown.value <= 0) {
      pollCountdown.value = POLL_SEC
    }
  }, 1000)
}

function startPolling() {
  stopPolling()
  startCountdown()
  pollTimer = window.setInterval(() => {
    loadStats().catch(() => {})
  }, POLL_MS)
}

function stopPolling() {
  stopCountdown()
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function barWidth(primary, total) {
  if (!total) return '0%'
  return `${Math.round((primary / total) * 100)}%`
}

function isFlashing(key) {
  return flashKeys.value.has(key)
}

onMounted(async () => {
  tickClock()
  clockTimer = window.setInterval(tickClock, 1000)
  await loadStats()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
  if (clockTimer) window.clearInterval(clockTimer)
})
</script>

<template>
  <div class="command-center">
    <div class="cc-bg">
      <div class="cc-orb orb-a" />
      <div class="cc-orb orb-b" />
      <div class="cc-orb orb-c" />
      <div class="cc-grid" />
    </div>

    <header class="cc-header">
      <div class="cc-brand">
        <span class="cc-icon">◈</span>
        <div>
          <h1>数据总览</h1>
          <p>{{ me?.email || 'COMMAND CENTER' }}</p>
        </div>
      </div>
      <div class="cc-meta">
        <span class="live-pill">
          <i />
          <span>LIVE ·</span>
          <RollingNumber :value="pollCountdown" size="sm" class="live-countdown" />
          <span>s</span>
        </span>
        <span class="clock">{{ clock }}</span>
      </div>
    </header>

    <SciFiActivityTicker :items="activityFeed" />

    <section class="cc-hero-grid">
      <SciFiDashPanel title="Event Stream · Follow" accent="green" :flash="isFlashing('follow')">
        <SciFiHeroMetric
          title="新关注"
          :value="stats.follow_today"
          :total="stats.follow_total"
          :delta="deltas.follow_today"
          :history="followHistory"
          color="#00ff9d"
          color2="#00f0ff"
          :flash="isFlashing('follow')"
        />
      </SciFiDashPanel>
      <SciFiDashPanel title="Event Stream · Join" accent="purple" :flash="isFlashing('join')">
        <SciFiHeroMetric
          title="进入直播间"
          :value="stats.join_today"
          :total="stats.join_total"
          :delta="deltas.join_today"
          :history="joinHistory"
          color="#a855f7"
          color2="#00f0ff"
          :flash="isFlashing('join')"
        />
      </SciFiDashPanel>
    </section>

    <section class="cc-ring-grid">
      <SciFiDashPanel title="Resource Matrix" subtitle="环形占用 · 实时同步" :flash="isFlashing('resources')">
        <div class="ring-row">
          <SciFiRingGauge
            label="监控任务"
            :primary="stats.active_task_count"
            :total="stats.total_task_count"
            primary-label="监控中"
            secondary-label="已停止"
            color="#00ff9d"
            color2="#475569"
          />
          <SciFiRingGauge
            label="API Key"
            :primary="stats.sign_key_in_use"
            :total="stats.sign_key_total"
            primary-label="使用中"
            secondary-label="未使用"
            color="#a855f7"
            color2="#475569"
          />
          <SciFiRingGauge
            label="机器人"
            :primary="stats.bot_pushing"
            :total="stats.bot_total"
            primary-label="推送中"
            secondary-label="闲置"
            color="#00f0ff"
            color2="#475569"
          />
          <SciFiRingGauge
            label="群组"
            :primary="stats.group_pushing"
            :total="stats.group_total"
            primary-label="推送中"
            secondary-label="闲置"
            color="#00ff9d"
            color2="#475569"
          />
        </div>
      </SciFiDashPanel>
    </section>

    <section class="cc-bars-grid">
      <SciFiDashPanel
        v-for="bar in resourceBars"
        :key="bar.key"
        :title="bar.label"
        :flash="isFlashing('resources')"
      >
        <div class="bar-head">
          <RollingNumber :value="bar.primary" size="md" />
          <span class="bar-sep">/</span>
          <span class="bar-total">{{ bar.total }}</span>
        </div>
        <div class="bar-track">
          <div
            class="bar-fill"
            :style="{ width: barWidth(bar.primary, bar.total), background: bar.color }"
          />
          <div class="bar-shine" />
        </div>
        <div class="bar-foot">
          <span>{{ bar.primaryLabel }} {{ bar.primary }}</span>
          <span>{{ bar.idleLabel }} {{ Math.max(bar.total - bar.primary, 0) }}</span>
        </div>
      </SciFiDashPanel>
    </section>
  </div>
</template>

<style scoped>
.command-center {
  position: relative;
  padding: 20px 24px 32px;
  min-height: 100%;
  overflow: hidden;
}

.cc-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.cc-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.35;
  animation: orb-float 12s ease-in-out infinite;
}

.orb-a {
  width: 280px;
  height: 280px;
  background: rgba(0, 240, 255, 0.15);
  top: -80px;
  left: -40px;
}

.orb-b {
  width: 320px;
  height: 320px;
  background: rgba(168, 85, 247, 0.12);
  top: 20%;
  right: -100px;
  animation-delay: -4s;
}

.orb-c {
  width: 240px;
  height: 240px;
  background: rgba(0, 255, 157, 0.1);
  bottom: 10%;
  left: 30%;
  animation-delay: -8s;
}

.cc-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 240, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 240, 255, 0.035) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 85%);
}

.cc-header,
.cc-ticker,
.cc-hero-grid,
.cc-ring-grid,
.cc-bars-grid {
  position: relative;
  z-index: 1;
}

.cc-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.cc-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.cc-icon {
  font-size: 2rem;
  color: var(--scifi-cyan);
  text-shadow: 0 0 24px rgba(0, 240, 255, 0.7);
  animation: icon-spin 8s linear infinite;
}

.cc-brand h1 {
  margin: 0;
  font-size: 1.35rem;
  color: var(--scifi-cyan);
  letter-spacing: 0.12em;
}

.cc-brand p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 0.9rem;
}

.cc-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.live-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-display);
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  color: var(--scifi-green);
  border: 1px solid rgba(0, 255, 157, 0.45);
  padding: 5px 12px;
  border-radius: 999px;
  box-shadow: 0 0 16px rgba(0, 255, 157, 0.2);
}

.live-pill :deep(.live-countdown.rolling-number) {
  font-size: 0.85rem;
  color: var(--scifi-green);
  text-shadow: 0 0 10px rgba(0, 255, 157, 0.5);
  min-width: 0.8em;
}

.live-pill i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--scifi-green);
  box-shadow: 0 0 10px var(--scifi-green);
  animation: live-blink 1.2s ease-in-out infinite;
}

.clock {
  font-family: var(--font-display);
  font-size: 0.78rem;
  color: #94a3b8;
  letter-spacing: 0.08em;
}

.cc-hero-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.cc-ring-grid {
  margin-bottom: 16px;
}

.ring-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.cc-bars-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.bar-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 10px;
}

.bar-sep {
  color: #64748b;
}

.bar-total {
  font-family: var(--font-display);
  font-size: 1.1rem;
  color: #94a3b8;
}

.bar-track {
  position: relative;
  height: 10px;
  border-radius: 999px;
  background: rgba(100, 116, 139, 0.25);
  overflow: hidden;
  margin-bottom: 10px;
}

.bar-fill {
  height: 100%;
  border-radius: 999px;
  box-shadow: 0 0 14px currentColor;
  transition: width 0.7s cubic-bezier(0.22, 1, 0.36, 1);
}

.bar-shine {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.25), transparent);
  animation: shine-move 2.5s linear infinite;
}

.bar-foot {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  color: #64748b;
}

@keyframes orb-float {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(12px, -16px); }
}

@keyframes icon-spin {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(180deg); }
}

@keyframes live-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

@keyframes shine-move {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(200%); }
}

@media (max-width: 1100px) {
  .ring-row,
  .cc-bars-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .command-center {
    padding: 16px;
  }

  .cc-hero-grid,
  .ring-row,
  .cc-bars-grid {
    grid-template-columns: 1fr;
  }
}
</style>
