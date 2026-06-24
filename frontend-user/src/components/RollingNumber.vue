<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  suffix: { type: String, default: '' },
  duration: { type: Number, default: 800 },
  size: { type: String, default: 'lg' },
})

const digits = ref(splitDigits(props.value))
const bump = ref(false)

function splitDigits(num) {
  return String(Math.max(0, Math.floor(num))).split('')
}

watch(
  () => props.value,
  (next, prev) => {
    digits.value = splitDigits(next)
    if (next !== prev) {
      bump.value = true
      window.setTimeout(() => {
        bump.value = false
      }, 420)
    }
  }
)

const digitTransforms = computed(() =>
  digits.value.map((d) => {
    const n = Number(d)
    return Number.isFinite(n) ? n : 0
  })
)
</script>

<template>
  <div class="rolling-number" :class="[size, { bump }]">
    <div class="rolling-digits" aria-live="polite">
      <span
        v-for="(digit, index) in digits"
        :key="`${index}-${digits.length}`"
        class="digit-slot"
      >
        <span
          class="digit-strip"
          :style="{
            transform: `translateY(calc(-1 * ${digitTransforms[index]} * var(--digit-height)))`,
            transitionDuration: `${duration}ms`,
          }"
        >
          <span v-for="n in 10" :key="n" class="digit">{{ n - 1 }}</span>
        </span>
      </span>
    </div>
    <span v-if="suffix" class="suffix">{{ suffix }}</span>
  </div>
</template>

<style scoped>
.rolling-number {
  --digit-height: 1.15em;
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  font-family: var(--font-display, 'Orbitron', system-ui, sans-serif);
  font-weight: 700;
  color: #00f0ff;
  text-shadow: 0 0 16px rgba(0, 240, 255, 0.45);
  transition: text-shadow 0.3s ease, transform 0.3s ease;
}

.rolling-number.lg {
  font-size: 2rem;
}

.rolling-number.md {
  font-size: 1.35rem;
}

.rolling-number.sm {
  font-size: 1rem;
}

.rolling-number.bump {
  text-shadow: 0 0 24px rgba(0, 240, 255, 0.75);
  transform: scale(1.02);
}

.rolling-digits {
  display: inline-flex;
  align-items: flex-end;
  line-height: 1;
}

.digit-slot {
  display: inline-block;
  height: var(--digit-height);
  overflow: hidden;
  min-width: 0.62em;
  text-align: center;
}

.digit-strip {
  display: flex;
  flex-direction: column;
  transition-property: transform;
  transition-timing-function: cubic-bezier(0.22, 1, 0.36, 1);
  will-change: transform;
}

.digit {
  height: var(--digit-height);
  line-height: var(--digit-height);
  display: block;
}

.suffix {
  font-family: var(--font-body, 'Rajdhani', system-ui, sans-serif);
  font-size: 0.75em;
  font-weight: 500;
  color: #94a3b8;
  margin-left: 2px;
}
</style>
