<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter, RouterView } from 'vue-router'
import { NIcon } from 'naive-ui'
import {
  PeopleOutline, StatsChartOutline, VideocamOutline, KeyOutline, HardwareChipOutline,
  ChatbubblesOutline,
} from '@vicons/ionicons5'
import SciFiShell from '../components/SciFiShell.vue'
import api from '../api'

const route = useRoute()
const router = useRouter()
const me = ref(null)

const email = computed(() => me.value?.email || localStorage.getItem('admin_email') || '')

const icon = (c) => () => h(NIcon, null, { default: () => h(c) })

const menuOptions = [
  { label: '用户管理', key: 'users', icon: icon(PeopleOutline) },
  { label: '监控主播', key: 'streamers', icon: icon(VideocamOutline) },
  { label: 'API Key', key: 'sign-keys', icon: icon(KeyOutline) },
  { label: '机器人', key: 'bots', icon: icon(HardwareChipOutline) },
  { label: '群组管理', key: 'groups', icon: icon(ChatbubblesOutline) },
  { label: '系统统计', key: 'stats', icon: icon(StatsChartOutline) },
]

const activeKey = computed(() => route.name)

async function loadMe() {
  const { data } = await api.get('/admin/api/me')
  me.value = data
  localStorage.setItem('admin_email', data.email)
}

function navigate(key) {
  router.push({ name: key })
}

function logout() {
  localStorage.removeItem('admin_token')
  localStorage.removeItem('admin_email')
  router.push('/login')
}

onMounted(loadMe)
</script>

<template>
  <SciFiShell
    brand="ADMIN PANEL"
    :email="email"
    :active-key="activeKey"
    :menu-options="menuOptions"
    @navigate="navigate"
    @logout="logout"
  >
    <RouterView />
  </SciFiShell>
</template>
