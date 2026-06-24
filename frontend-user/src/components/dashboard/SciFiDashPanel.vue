<script setup>
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  flash: { type: Boolean, default: false },
  accent: { type: String, default: 'cyan' },
})
</script>

<template>
  <div class="dash-panel scifi-card" :class="[`accent-${accent}`, { flash }]">
    <div class="panel-scan" />
    <div class="panel-grid" />
    <div v-if="title" class="panel-head">
      <div class="panel-title">{{ title }}</div>
      <div v-if="subtitle" class="panel-sub">{{ subtitle }}</div>
    </div>
    <div class="panel-body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.dash-panel {
  position: relative;
  overflow: hidden;
  padding: 16px 18px;
  min-height: 120px;
}

.panel-scan {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  top: 0;
  background: linear-gradient(90deg, transparent, rgba(0, 240, 255, 0.8), transparent);
  animation: scan-move 4s linear infinite;
  opacity: 0.45;
  pointer-events: none;
}

.panel-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 240, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 240, 255, 0.03) 1px, transparent 1px);
  background-size: 18px 18px;
  mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.5), transparent 85%);
  pointer-events: none;
}

.panel-head {
  position: relative;
  z-index: 1;
  margin-bottom: 12px;
}

.panel-title {
  font-family: var(--font-display);
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  color: var(--scifi-cyan);
  text-transform: uppercase;
}

.panel-sub {
  margin-top: 4px;
  font-size: 0.82rem;
  color: #64748b;
}

.panel-body {
  position: relative;
  z-index: 1;
}

.dash-panel.flash {
  animation: panel-pulse 0.75s ease;
}

.accent-green .panel-title { color: var(--scifi-green); }
.accent-purple .panel-title { color: var(--scifi-purple); }
.accent-green .panel-scan {
  background: linear-gradient(90deg, transparent, rgba(0, 255, 157, 0.85), transparent);
}
.accent-purple .panel-scan {
  background: linear-gradient(90deg, transparent, rgba(168, 85, 247, 0.85), transparent);
}

@keyframes scan-move {
  0% { transform: translateY(0); opacity: 0; }
  10% { opacity: 0.5; }
  90% { opacity: 0.5; }
  100% { transform: translateY(220px); opacity: 0; }
}

@keyframes panel-pulse {
  0% { box-shadow: 0 0 20px rgba(0, 240, 255, 0.08), inset 0 0 30px rgba(0, 240, 255, 0.02); }
  40% {
    box-shadow:
      0 0 28px rgba(0, 240, 255, 0.35),
      0 0 48px rgba(0, 255, 157, 0.15),
      inset 0 0 40px rgba(0, 240, 255, 0.08);
    border-color: rgba(0, 240, 255, 0.65);
  }
  100% { box-shadow: 0 0 20px rgba(0, 240, 255, 0.08), inset 0 0 30px rgba(0, 240, 255, 0.02); }
}
</style>
