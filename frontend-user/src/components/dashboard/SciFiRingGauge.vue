<script setup>
import { computed, ref, watch } from 'vue'
import RollingNumber from '../RollingNumber.vue'

const props = defineProps({
  label: { type: String, required: true },
  primary: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  primaryLabel: { type: String, default: '活跃' },
  secondaryLabel: { type: String, default: '其他' },
  color: { type: String, default: '#00f0ff' },
  color2: { type: String, default: '#334155' },
})

const pulse = ref(false)
const gaugeId = `rg-${Math.random().toString(36).slice(2, 9)}`
const size = 128
const stroke = 9
const radius = (size - stroke) / 2
const circumference = 2 * Math.PI * radius

const ratio = computed(() => {
  if (!props.total) return 0
  return Math.min(props.primary / props.total, 1)
})

const dashPrimary = computed(() => `${circumference * ratio.value} ${circumference}`)

const percentText = computed(() => {
  if (!props.total) return '0%'
  return `${Math.round(ratio.value * 100)}%`
})

watch(
  () => [props.primary, props.total],
  () => {
    pulse.value = true
    window.setTimeout(() => { pulse.value = false }, 700)
  }
)
</script>

<template>
  <div class="ring-gauge" :class="{ pulse }">
    <div class="ring-wrap">
      <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" class="ring-svg">
        <defs>
          <filter :id="gaugeId" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <circle
          class="ring-track"
          :cx="size / 2"
          :cy="size / 2"
          :r="radius"
          :stroke-width="stroke"
        />
        <circle
          class="ring-seg ring-seg-primary"
          :cx="size / 2"
          :cy="size / 2"
          :r="radius"
          :stroke="color"
          :stroke-width="stroke"
          :stroke-dasharray="dashPrimary"
          :transform="`rotate(-90 ${size / 2} ${size / 2})`"
          :filter="`url(#${gaugeId})`"
        />
      </svg>
      <div class="ring-center">
        <div class="ring-percent">{{ percentText }}</div>
        <div class="ring-ratio">
          <RollingNumber :value="primary" size="sm" />
          <span class="sep">/</span>
          <span class="total-num">{{ total }}</span>
        </div>
      </div>
    </div>
    <div class="ring-label">{{ label }}</div>
    <div class="ring-legend">
      <span><i :style="{ background: color }" />{{ primaryLabel }} {{ primary }}</span>
      <span><i :style="{ background: color2 }" />{{ secondaryLabel }} {{ Math.max(total - primary, 0) }}</span>
    </div>
  </div>
</template>

<style scoped>
.ring-gauge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  transition: transform 0.35s ease, filter 0.35s ease;
}

.ring-gauge.pulse {
  transform: scale(1.03);
  filter: drop-shadow(0 0 14px rgba(0, 240, 255, 0.45));
}

.ring-wrap {
  position: relative;
  width: 128px;
  height: 128px;
}

.ring-svg {
  display: block;
}

.ring-track {
  fill: none;
  stroke: rgba(100, 116, 139, 0.35);
}

.ring-seg {
  fill: none;
  stroke-linecap: round;
  transition: stroke-dasharray 0.7s cubic-bezier(0.22, 1, 0.36, 1);
}

.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.ring-percent {
  font-family: var(--font-display);
  font-size: 1.05rem;
  color: #e2e8f0;
  letter-spacing: 0.06em;
}

.ring-ratio {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 2px;
  margin-top: 2px;
}

.sep, .total-num {
  font-family: var(--font-display);
  font-size: 0.72rem;
  color: #64748b;
}

.ring-label {
  font-family: var(--font-display);
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  color: var(--scifi-cyan);
  text-transform: uppercase;
}

.ring-legend {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.78rem;
  color: #94a3b8;
}

.ring-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ring-legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 6px currentColor;
}
</style>
