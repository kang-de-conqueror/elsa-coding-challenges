<script setup lang="ts">
import { computed } from 'vue'
import { useQuizStore } from '@/stores/quiz'

const store = useQuizStore()

const label = computed(() => {
  switch (store.connectionStatus) {
    case 'open':
      return 'Connected'
    case 'connecting':
      return 'Connecting…'
    case 'reconnecting':
      return 'Reconnecting…'
    case 'closed':
      return 'Disconnected'
    default:
      return 'Idle'
  }
})
</script>

<template>
  <span class="status" :class="store.connectionStatus" role="status">
    <span class="dot" aria-hidden="true" />
    {{ label }}
  </span>
</template>

<style scoped>
.status {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  font-weight: 600;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: var(--color-background-mute);
}

.dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  background: currentColor;
}

.status.open {
  color: #1a7f37;
}
.status.connecting,
.status.reconnecting {
  color: #9a6700;
}
.status.closed,
.status.idle {
  color: #cf222e;
}
</style>
