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
  gap: 0.45rem;
  font-size: 0.8rem;
  font-weight: 700;
  padding: 0.3rem 0.75rem;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--border);
}

.dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: currentColor;
}

.status.open {
  color: var(--success);
}
.status.open .dot {
  box-shadow: 0 0 0 0 currentColor;
  animation: ping 2s infinite;
}
.status.connecting,
.status.reconnecting {
  color: var(--warning);
}
.status.closed,
.status.idle {
  color: var(--danger);
}

@keyframes ping {
  0% {
    box-shadow: 0 0 0 0 rgba(18, 160, 106, 0.55);
  }
  70%,
  100% {
    box-shadow: 0 0 0 7px rgba(18, 160, 106, 0);
  }
}
</style>
