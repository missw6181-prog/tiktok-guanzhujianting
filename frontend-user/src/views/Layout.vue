<script setup>
import { computed, h, onMounted, provide, ref } from 'vue'
import { useRoute, useRouter, RouterView } from 'vue-router'
import { NIcon } from 'naive-ui'
import {
  VideocamOutline,
  KeyOutline,
  HardwareChipOutline,
  PeopleOutline,
  PulseOutline,
  GridOutline,
} from '@vicons/ionicons5'
import SciFiShell from '../components/SciFiShell.vue'
import api from '../api'

const route = useRoute()
const router = useRouter()
const me = ref(null)

const email = computed(() => me.value?.email || localStorage.getItem('user_email') || '')
const quota = computed(() => {
  if (!me.value) return ''
  return `任务 ${me.value.monitor_count}/${me.value.max_monitors}`
})

const icon = (c) => () => h(NIcon, null, { default: () => h(c) })

const menuOptions = [
  { label: '数据总览', key: 'overview', icon: icon(GridOutline) },
  { label: '监控任务', key: 'tasks', icon: icon(VideocamOutline) },
  { label: 'API Key 池', key: 'sign-keys', icon: icon(KeyOutline) },
  { label: '机器人', key: 'bots', icon: icon(HardwareChipOutline) },
  { label: '群组', key: 'groups', icon: icon(PeopleOutline) },
  { label: '事件流水', key: 'events', icon: icon(PulseOutline) },
]

const activeKey = computed(() => route.name)

async function loadMe() {
  const { data } = await api.get('/api/me')
  me.value = data
  localStorage.setItem('user_email', data.email)
}

provide('me', me)
provide('reloadMe', loadMe)

function navigate(key) {
  router.push({ name: key })
}

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user_email')
  router.push('/login')
}

onMounted(loadMe)
</script>

<template>
  <SciFiShell
    brand="LIVE MONITOR"
    :email="email"
    :quota="quota"
    :active-key="activeKey"
    :menu-options="menuOptions"
    @navigate="navigate"
    @logout="logout"
  >
    <RouterView />
  </SciFiShell>
</template>
