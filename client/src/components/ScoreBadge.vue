<script setup lang="ts">
import { useQuizStore } from '@/stores/quiz'

const store = useQuizStore()
</script>

<template>
  <div class="score-badge">
    <span class="label">{{ store.username }}</span>
    <span class="score">{{ store.myScore }} pts</span>
    <span v-if="store.myRank" class="rank">rank #{{ store.myRank }}</span>
  </div>
</template>

<style scoped>
.score-badge {
  display: inline-flex;
  align-items: baseline;
  gap: 0.6rem;
  padding: 0.5rem 0.9rem;
  border-radius: 999px;
  background: var(--color-background-soft);
  font-weight: 600;
}
.score {
  color: hsla(160, 100%, 30%, 1);
}
.rank {
  font-size: 0.85rem;
  opacity: 0.75;
}
</style>
