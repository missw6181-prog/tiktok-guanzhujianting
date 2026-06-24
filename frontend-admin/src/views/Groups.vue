<script setup>
import { NCard } from 'naive-ui'
import AdminGroupsPanel from '../components/AdminGroupsPanel.vue'
</script>

<template>
  <div class="page-container">
    <NCard class="scifi-card table-scroll" :bordered="false">
      <AdminGroupsPanel />
    </NCard>
  </div>
</template>
