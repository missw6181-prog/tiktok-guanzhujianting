<script setup>
import { computed, ref, watch } from 'vue'
import RollingNumber from './RollingNumber.vue'

const props = defineProps({
  title: { type: String, default: '' },
  items: {
    type: Array,
    default: () => [],
  },
})

const flashing = ref(new Set())
const prevSnap = ref('')

const maxValue = computed(() => {
  const values = props.items.map((i) => i.value)
  return Math.max(...values, 1)
})

function barHeight(value) {
  return `${Math.round((value / maxValue.value) * 100)}%`
}

function isFlashing(label) {
  return flashing.value.has(label)
}

watch(
  () => props.items.map((i) => `${i.label}:${i.value}`).join('|'),
  (snap) => {
    if (!prevSnap.value) {
      prevSnap.value = snap
      return
    }
    if (snap === prevSnap.value) return

    const prevMap = Object.fromEntries(
      prevSnap.value.split('|').filter(Boolean).map((part) => {
        const idx = part.indexOf(':')
        return [part.slice(0, idx), Number(part.slice(idx + 1))]
      })
    )
    props.items.forEach((item) => {
      if (prevMap[item.label] !== undefined && prevMap[item.label] !== item.value) {
        flashing.value.add(item.label)
        flashing.value = new Set(flashing.value)
        window.setTimeout(() => {
          flashing.value.delete(item.label)
          flashing.value = new Set(flashing.value)
        }, 700)
      }
    })
    prevSnap.value = snap
  }
)
</script>

<template>
  <div class="stat-bar-chart">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div class="chart-body">
      <div
        v-for="item in items"
        :key="item.label"
        class="bar-col"
        :class="{ flash: isFlashing(item.label) }"
      >
        <div class="bar-value">
          <RollingNumber :value="item.value" size="sm" />
        </div>
        <div class="bar-track" :class="{ flash: isFlashing(item.label) }">
          <div
            class="bar-fill"
            :style="{ height: barHeight(item.value), background: item.color }"
          />
        </div>
        <div class="bar-label">{{ item.label }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stat-bar-chart {
  height: 100%;
}

.chart-title {
  margin-bottom: 16px;
  font-family: var(--font-display);
  font-size: 0.85rem;
  letter-spacing: 0.08em;
  color: var(--scifi-cyan);
  text-transform: uppercase;
}

.chart-body {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 16px;
  min-height: 220px;
  padding: 0 8px 4px;
}

.bar-col {
  flex: 1;
  max-width: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-width: 0;
  transition: filter 0.25s ease;
}

.bar-col.flash {
  filter: drop-shadow(0 0 10px rgba(0, 240, 255, 0.55));
}

.bar-value {
  min-height: 1.2em;
}

.bar-track {
  width: 100%;
  height: 160px;
  display: flex;
  align-items: flex-end;
  border: 1px solid rgba(0, 240, 255, 0.15);
  background: rgba(0, 240, 255, 0.03);
  border-radius: 4px 4px 0 0;
  padding: 4px;
  transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
}

.bar-track.flash {
  border-color: rgba(0, 240, 255, 0.65);
  background: rgba(0, 240, 255, 0.1);
  box-shadow: 0 0 18px rgba(0, 240, 255, 0.35), inset 0 0 12px rgba(0, 240, 255, 0.12);
}

.bar-fill {
  width: 100%;
  min-height: 4px;
  border-radius: 2px 2px 0 0;
  box-shadow: 0 0 12px currentColor;
  transition: height 0.6s ease, filter 0.25s ease, box-shadow 0.25s ease;
}

.bar-col.flash .bar-fill {
  filter: brightness(1.35) saturate(1.2);
  box-shadow: 0 0 22px currentColor, 0 0 8px #fff;
}

.bar-label {
  font-size: 0.9rem;
  color: #94a3b8;
  text-align: center;
  word-break: break-word;
  transition: color 0.25s ease;
}

.bar-col.flash .bar-label {
  color: #e2e8f0;
}
</style>
