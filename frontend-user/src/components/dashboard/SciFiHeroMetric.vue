<script setup>
import RollingNumber from '../RollingNumber.vue'
import SciFiSparkline from './SciFiSparkline.vue'

defineProps({
  title: { type: String, required: true },
  value: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  delta: { type: Number, default: 0 },
  history: { type: Array, default: () => [] },
  color: { type: String, default: '#00ff9d' },
  color2: { type: String, default: '#00f0ff' },
  flash: { type: Boolean, default: false },
})
</script>

<template>
  <div class="hero-metric" :class="{ flash }">
    <div class="hero-glow" :style="{ background: `radial-gradient(circle, ${color}22 0%, transparent 70%)` }" />
    <div class="hero-top">
      <span class="hero-title">{{ title }}</span>
      <span v-if="delta > 0" class="hero-delta">+{{ delta }}</span>
    </div>
    <div class="hero-main">
      <RollingNumber :value="value" size="lg" />
      <span class="hero-unit">今日</span>
    </div>
    <div class="hero-sub">
      累计
      <RollingNumber :value="total" size="sm" />
    </div>
    <SciFiSparkline :data="history" :color="color" :color2="color2" :height="64" />
  </div>
</template>

<style scoped>
.hero-metric {
  position: relative;
  padding: 4px 0 0;
  transition: filter 0.35s ease;
}

.hero-metric.flash {
  filter: drop-shadow(0 0 16px rgba(0, 255, 157, 0.35));
}

.hero-glow {
  position: absolute;
  top: -20px;
  left: 50%;
  transform: translateX(-50%);
  width: 180px;
  height: 100px;
  pointer-events: none;
}

.hero-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.hero-title {
  font-family: var(--font-display);
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  color: var(--scifi-cyan);
  text-transform: uppercase;
}

.hero-delta {
  font-family: var(--font-display);
  font-size: 0.85rem;
  color: var(--scifi-green);
  padding: 2px 8px;
  border: 1px solid rgba(0, 255, 157, 0.45);
  border-radius: 999px;
  animation: delta-pop 0.5s ease;
  box-shadow: 0 0 12px rgba(0, 255, 157, 0.3);
}

.hero-main {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.hero-unit {
  font-size: 0.9rem;
  color: #64748b;
}

.hero-sub {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 6px 0 12px;
  font-size: 0.88rem;
  color: #94a3b8;
}

@keyframes delta-pop {
  0% { transform: scale(0.8); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}
</style>
