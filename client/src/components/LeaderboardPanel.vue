<script setup lang="ts">
import { computed } from 'vue'
import { useQuizStore } from '@/stores/quiz'
import UserAvatar from '@/components/UserAvatar.vue'

const store = useQuizStore()

withDefaults(defineProps<{ title?: string; live?: boolean }>(), { title: undefined, live: true })

const MEDALS = ['🥇', '🥈', '🥉']
const topScore = computed(() => Math.max(1, ...store.leaderboard.map((entry) => entry.score)))
</script>

<template>
  <div class="leaderboard card">
    <div class="head">
      <h3>{{ title ?? 'Leaderboard' }}</h3>
      <span v-if="live" class="live"><span class="dot" aria-hidden="true" />Live</span>
    </div>

    <TransitionGroup name="rank" tag="ol">
      <li
        v-for="entry in store.leaderboard"
        :key="entry.user_id"
        :class="{ me: entry.user_id === store.userId }"
      >
        <span class="rank">
          <template v-if="entry.rank <= 3 && entry.score > 0">{{ MEDALS[entry.rank - 1] }}</template>
          <template v-else>#{{ entry.rank }}</template>
        </span>
        <UserAvatar :name="entry.username" :size="32" />
        <span class="body">
          <span class="name">{{ entry.username }}</span>
          <span class="bar"><span class="fill" :style="{ width: (entry.score / topScore) * 100 + '%' }" /></span>
        </span>
        <span class="score">{{ entry.score }}</span>
      </li>
    </TransitionGroup>

    <p v-if="store.leaderboard.length === 0" class="empty">Scores will appear here as players answer.</p>
  </div>
</template>

<style scoped>
.leaderboard {
  padding: 1.25rem;
  min-width: 280px;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.8rem;
}
.live {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--success);
}
.live .dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  background: currentColor;
}
ol {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.35rem;
  position: relative;
}
li {
  display: grid;
  grid-template-columns: 2.1rem 32px minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.6rem;
  border-radius: var(--radius-sm);
  background: var(--surface);
}
li.me {
  background: var(--primary-soft);
  box-shadow: inset 0 0 0 2px var(--primary);
}
.rank {
  text-align: center;
  font-weight: 800;
  font-size: 1rem;
  color: var(--text-muted);
}
.body {
  display: grid;
  gap: 0.25rem;
  min-width: 0;
}
.name {
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bar {
  display: block;
  height: 5px;
  border-radius: 999px;
  background: var(--surface-2);
  overflow: hidden;
}
.fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), var(--primary));
  transition: width 0.5s ease;
}
.score {
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.empty {
  margin: 0.5rem 0 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.rank-move {
  transition: transform 0.45s ease;
}
.rank-enter-active {
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}
.rank-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.rank-leave-active {
  position: absolute;
  opacity: 0;
}
</style>
