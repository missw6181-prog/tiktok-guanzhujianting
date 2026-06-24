<template>
  <NLayout class="app-layout" has-sider>
    <NLayoutSider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      :collapsed="collapsed"
      show-trigger
      class="app-sider"
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <div class="brand" :class="{ collapsed }">
        <span class="brand-icon">◈</span>
        <span v-if="!collapsed" class="brand-text scifi-glow">{{ brand }}</span>
      </div>
      <NMenu
        :value="activeKey"
        :collapsed="collapsed"
        :collapsed-width="64"
        :options="menuOptions"
        @update:value="(k) => emit('navigate', k)"
      />
      <div v-if="quota" class="quota-bar" :class="{ collapsed }">
        <span v-if="!collapsed">{{ quota }}</span>
      </div>
      <div class="sider-footer">
        <div v-if="!collapsed" class="user-email">{{ email }}</div>
        <NButton quaternary circle @click="emit('logout')">
          <template #icon><NIcon><LogOutOutline /></NIcon></template>
        </NButton>
      </div>
    </NLayoutSider>
    <NLayout>
      <NLayoutContent class="app-content">
        <slot />
      </NLayoutContent>
    </NLayout>
  </NLayout>
</template>

<script setup>
import { ref } from 'vue'
import { NLayout, NLayoutSider, NLayoutContent, NMenu, NButton, NIcon } from 'naive-ui'
import { LogOutOutline } from '@vicons/ionicons5'

defineProps({
  brand: { type: String, required: true },
  email: { type: String, default: '' },
  quota: { type: String, default: '' },
  activeKey: { type: String, required: true },
  menuOptions: { type: Array, required: true },
})
const emit = defineEmits(['navigate', 'logout'])
const collapsed = ref(false)
</script>

<style scoped>
.app-layout { min-height: 100vh; }
.app-sider {
  background: rgba(10, 14, 23, 0.95) !important;
  border-right: 1px solid rgba(0, 240, 255, 0.15) !important;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 20px 16px; border-bottom: 1px solid rgba(0, 240, 255, 0.1); }
.brand.collapsed { justify-content: center; padding: 20px 0; }
.brand-icon { color: #00f0ff; font-size: 1.4rem; text-shadow: 0 0 10px rgba(0, 240, 255, 0.6); }
.brand-text { font-family: var(--font-display); font-size: 0.85rem; font-weight: 700; color: #00f0ff; letter-spacing: 0.15em; }
.quota-bar {
  padding: 8px 16px;
  font-size: 0.75rem;
  color: #64748b;
  border-bottom: 1px solid rgba(0, 240, 255, 0.08);
}
.quota-bar.collapsed { padding: 8px 0; text-align: center; }
.sider-footer {
  position: absolute; bottom: 0; left: 0; right: 0; padding: 16px;
  display: flex; align-items: center; justify-content: space-between;
  border-top: 1px solid rgba(0, 240, 255, 0.1);
}
.user-email { font-size: 0.85rem; color: #94a3b8; word-break: break-all; max-width: 140px; }
.app-content { min-height: 100vh; overflow-x: hidden; }
</style>
