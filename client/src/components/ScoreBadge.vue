<script setup lang="ts">
import { useQuizStore } from '@/stores/quiz'
import UserAvatar from '@/components/UserAvatar.vue'

const store = useQuizStore()
</script>

<template>
  <div class="score-badge">
    <UserAvatar :name="store.username" :size="34" />
    <div class="info">
      <span class="name">{{ store.username }}</span>
      <span v-if="store.myRank" class="rank">Rank #{{ store.myRank }}</span>
    </div>
    <span class="score">{{ store.myScore }}<small>pts</small></span>
  </div>
</template>

<style scoped>
.score-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.4rem 1rem 0.4rem 0.45rem;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}
.info {
  display: grid;
  line-height: 1.15;
}
.name {
  font-weight: 700;
  font-size: 0.9rem;
}
.rank {
  font-size: 0.72rem;
  color: var(--text-muted);
}
.score {
  font-weight: 800;
  font-size: 1.15rem;
  color: var(--primary);
  font-variant-numeric: tabular-nums;
}
.score small {
  margin-left: 0.15rem;
  font-size: 0.65rem;
  color: var(--text-muted);
  font-weight: 700;
}
</style>
