<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  color: { type: String, default: '#00f0ff' },
  color2: { type: String, default: '#a855f7' },
  height: { type: Number, default: 72 },
  width: { type: Number, default: 320 },
})

const pulseEnd = ref(false)
const uid = `sp-${Math.random().toString(36).slice(2, 9)}`

const points = computed(() => {
  const w = props.width
  const h = props.height
  const pad = 4
  const vals = props.data.length ? props.data : [0]
  const max = Math.max(...vals, 1)
  const min = Math.min(...vals, 0)
  const range = max - min || 1

  return vals.map((v, i) => {
    const x = pad + (i / Math.max(vals.length - 1, 1)) * (w - pad * 2)
    const y = h - pad - ((v - min) / range) * (h - pad * 2)
    return { x, y }
  })
})

const linePath = computed(() => {
  if (!points.value.length) return ''
  return points.value.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ')
})

const areaPath = computed(() => {
  if (!points.value.length) return ''
  const first = points.value[0]
  const last = points.value[points.value.length - 1]
  return `${linePath.value} L ${last.x} ${props.height} L ${first.x} ${props.height} Z`
})

const endDot = computed(() => points.value[points.value.length - 1] || { x: 0, y: 0 })

watch(
  () => props.data[props.data.length - 1],
  () => {
    pulseEnd.value = true
    window.setTimeout(() => { pulseEnd.value = false }, 600)
  }
)
</script>

<template>
  <svg :width="width" :height="height" :viewBox="`0 0 ${width} ${height}`" class="sparkline">
    <defs>
      <linearGradient :id="uid" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="color" stop-opacity="0.45" />
        <stop offset="100%" :stop-color="color" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path v-if="areaPath" class="spark-area" :d="areaPath" :fill="`url(#${uid})`" />
    <path v-if="linePath" class="spark-line" :d="linePath" :stroke="color" />
    <circle
      class="spark-dot"
      :class="{ pulse: pulseEnd }"
      :cx="endDot.x"
      :cy="endDot.y"
      r="4"
      :fill="color2"
    />
  </svg>
</template>

<style scoped>
.sparkline {
  width: 100%;
  height: auto;
  display: block;
}

.spark-line {
  fill: none;
  stroke-width: 2;
  filter: drop-shadow(0 0 4px currentColor);
  transition: d 0.5s ease;
}

.spark-area {
  transition: d 0.5s ease;
}

.spark-dot {
  filter: drop-shadow(0 0 6px currentColor);
  transition: r 0.3s ease;
}

.spark-dot.pulse {
  animation: dot-pulse 0.6s ease;
}

@keyframes dot-pulse {
  0% { r: 4; opacity: 1; }
  50% { r: 7; opacity: 0.85; }
  100% { r: 4; opacity: 1; }
}
</style>
