<script setup lang="ts">
import { useQuizStore } from '@/stores/quiz'

const store = useQuizStore()

defineProps<{ title?: string }>()
</script>

<template>
  <div class="leaderboard">
    <h3>{{ title ?? 'Leaderboard' }}</h3>
    <ol>
      <li
        v-for="entry in store.leaderboard"
        :key="entry.user_id"
        :class="{ me: entry.user_id === store.userId }"
      >
        <span class="rank">#{{ entry.rank }}</span>
        <span class="name">{{ entry.username }}</span>
        <span class="score">{{ entry.score }}</span>
      </li>
    </ol>
    <p v-if="store.leaderboard.length === 0" class="empty">No scores yet.</p>
  </div>
</template>

<style scoped>
.leaderboard {
  padding: 1.25rem;
  border-radius: 12px;
  background: var(--color-background-soft);
  min-width: 260px;
}
ol {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
  display: grid;
  gap: 0.4rem;
}
li {
  display: grid;
  grid-template-columns: 2.5rem 1fr auto;
  align-items: center;
  padding: 0.5rem 0.6rem;
  border-radius: 8px;
}
li.me {
  background: hsla(160, 100%, 37%, 0.15);
  font-weight: 700;
}
.rank {
  color: var(--color-text);
  opacity: 0.7;
}
.score {
  font-variant-numeric: tabular-nums;
}
.empty {
  opacity: 0.7;
  font-size: 0.9rem;
}
</style>
