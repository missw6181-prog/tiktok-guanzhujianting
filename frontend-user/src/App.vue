<script setup>
import { RouterView } from 'vue-router'
import { NConfigProvider, NDialogProvider, NMessageProvider, darkTheme } from 'naive-ui'
import { scifiThemeOverrides } from '@shared/theme/scifi.js'
</script>

<template>
  <NConfigProvider :theme="darkTheme" :theme-overrides="scifiThemeOverrides">
    <NDialogProvider>
      <NMessageProvider>
        <RouterView />
      </NMessageProvider>
    </NDialogProvider>
  </NConfigProvider>
</template>
