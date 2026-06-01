<template>
  <span class="inline-flex items-center gap-2.5 select-none">
    <svg :width="size" :height="size" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient :id="gid" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#003087" />
          <stop offset="100%" stop-color="#0066cc" />
        </linearGradient>
      </defs>
      <rect width="100" height="100" rx="22" :fill="`url(#${gid})`" />
      <path
        fill-rule="evenodd"
        d="M 50 10 L 87 90 L 75 90 L 65 64 L 35 64 L 25 90 L 13 90 Z
           M 50 24 L 62 58 L 38 58 Z"
        fill="white"
      />
    </svg>
    <span v-if="wordmark" class="font-semibold tracking-tight" :style="{ fontSize: wordSize, color: 'var(--text)' }">
      K<span style="color:var(--text-3)">.</span>I<span style="color:var(--text-3)">.</span>A
    </span>
  </span>
</template>

<script setup>
defineProps({
  size: { type: [Number, String], default: 28 },
  wordmark: { type: Boolean, default: true },
  wordSize: { type: String, default: '1.15rem' },
})
// unique gradient id so multiple logos on a page don't clash
const gid = 'kia-grad-' + Math.random().toString(36).slice(2, 8)
</script>
