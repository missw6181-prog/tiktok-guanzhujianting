<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})

const wallHit = ref(false)
let lastHeadId = null

watch(
  () => props.items[0]?.id,
  (id) => {
    if (id == null || id === lastHeadId) return
    lastHeadId = id
    wallHit.value = false
    requestAnimationFrame(() => {
      wallHit.value = true
      window.setTimeout(() => {
        wallHit.value = false
      }, 520)
    })
  },
  { immediate: true }
)
</script>

<template>
  <div v-if="items.length" class="activity-ticker">
    <span class="ticker-label">实时动态</span>
    <div class="ticker-wall" :class="{ hit: wallHit }">
      <span class="wall-core" />
      <span class="wall-spark spark-a" />
      <span class="wall-spark spark-b" />
    </div>
    <div class="ticker-track">
      <TransitionGroup name="ticker-crash" tag="div" class="ticker-list">
        <span
          v-for="item in items"
          :key="item.id"
          class="ticker-item"
          :class="item.type"
        >
          <span class="item-time">{{ item.time }}</span>
          <span class="item-dot">·</span>
          <span class="item-text">{{ item.text }}</span>
        </span>
      </TransitionGroup>
    </div>
  </div>
</template>

<style scoped>
.activity-ticker {
  display: flex;
  align-items: stretch;
  gap: 0;
  margin-bottom: 16px;
  padding: 10px 14px 10px 12px;
  border: 1px solid rgba(0, 240, 255, 0.2);
  background: rgba(0, 240, 255, 0.04);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.ticker-label {
  flex-shrink: 0;
  align-self: center;
  padding-right: 12px;
  font-family: var(--font-display);
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  color: var(--scifi-cyan);
  z-index: 2;
}

.ticker-wall {
  position: relative;
  flex-shrink: 0;
  width: 3px;
  align-self: stretch;
  margin-right: 10px;
  z-index: 2;
}

.wall-core {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    transparent,
    rgba(0, 240, 255, 0.65) 20%,
    rgba(0, 255, 157, 0.85) 50%,
    rgba(0, 240, 255, 0.65) 80%,
    transparent
  );
  box-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
  transition: box-shadow 0.2s ease, filter 0.2s ease;
}

.ticker-wall.hit .wall-core {
  box-shadow:
    0 0 16px rgba(0, 255, 157, 0.9),
    0 0 32px rgba(0, 240, 255, 0.6);
  filter: brightness(1.6);
}

.wall-spark {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  pointer-events: none;
  opacity: 0;
}

.ticker-wall.hit .wall-spark {
  animation: spark-burst 0.5s ease-out forwards;
}

.spark-a {
  background: radial-gradient(circle, rgba(0, 255, 157, 0.9) 0%, transparent 70%);
}

.spark-b {
  background: radial-gradient(circle, rgba(0, 240, 255, 0.85) 0%, transparent 70%);
  animation-delay: 0.05s;
}

.ticker-track {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  align-self: center;
}

.ticker-list {
  display: flex;
  align-items: center;
  gap: 16px;
  white-space: nowrap;
}

.ticker-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.85rem;
  color: #cbd5e1;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(100, 116, 139, 0.35);
}

.ticker-item.follow {
  border-color: rgba(0, 255, 157, 0.35);
  box-shadow: inset 0 0 12px rgba(0, 255, 157, 0.08);
}

.ticker-item.join {
  border-color: rgba(168, 85, 247, 0.35);
  box-shadow: inset 0 0 12px rgba(168, 85, 247, 0.08);
}

.item-time {
  font-family: var(--font-display);
  font-size: 0.72rem;
  color: #64748b;
  letter-spacing: 0.04em;
}

.item-dot {
  color: #475569;
}

.item-text {
  font-weight: 600;
}

.ticker-item.follow .item-text {
  color: var(--scifi-green);
  text-shadow: 0 0 8px rgba(0, 255, 157, 0.35);
}

.ticker-item.join .item-text {
  color: #c4b5fd;
  text-shadow: 0 0 8px rgba(168, 85, 247, 0.35);
}

/* 从左撞入 + 回弹 */
.ticker-crash-enter-active {
  animation: crash-in 0.62s cubic-bezier(0.22, 1.15, 0.36, 1);
}

.ticker-crash-leave-active {
  position: absolute;
  animation: crash-out 0.35s ease forwards;
}

.ticker-crash-move {
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes crash-in {
  0% {
    opacity: 0;
    transform: translateX(calc(-100% - 80px)) scale(0.75);
    filter: brightness(2);
  }
  55% {
    opacity: 1;
    transform: translateX(6px) scale(1.08);
    filter: brightness(1.45);
  }
  72% {
    transform: translateX(-5px) scale(0.97);
    filter: brightness(1.1);
  }
  88% {
    transform: translateX(2px) scale(1.02);
  }
  100% {
    transform: translateX(0) scale(1);
    filter: brightness(1);
  }
}

@keyframes crash-out {
  to {
    opacity: 0;
    transform: translateX(40px) scale(0.9);
  }
}

@keyframes spark-burst {
  0% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.2);
  }
  35% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(2.2);
  }
  100% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(3);
  }
}
</style>
