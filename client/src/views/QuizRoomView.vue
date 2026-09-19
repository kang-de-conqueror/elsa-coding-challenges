<script setup lang="ts">
import { useQuizStore } from '@/stores/quiz'
import { useQuizSocket } from '@/composables/useQuizSocket'
import ConnectionStatus from '@/components/ConnectionStatus.vue'
import ScoreBadge from '@/components/ScoreBadge.vue'
import QuestionCard from '@/components/QuestionCard.vue'
import LeaderboardPanel from '@/components/LeaderboardPanel.vue'

const store = useQuizStore()
const { start, leave } = useQuizSocket()
</script>

<template>
  <div class="quiz-room">
    <header>
      <div>
        <h1>Quiz: {{ store.quizId }}</h1>
        <ConnectionStatus />
      </div>
      <div class="header-right">
        <ScoreBadge v-if="store.phase !== 'lobby'" />
        <button type="button" class="leave" @click="leave">Leave</button>
      </div>
    </header>

    <p v-if="store.errorMessage" class="error">{{ store.errorMessage }}</p>

    <section v-if="store.phase === 'lobby'" class="lobby">
      <h2>Waiting for players…</h2>
      <ul class="participants">
        <li v-for="p in store.participants" :key="p.user_id" :class="{ offline: !p.connected }">
          {{ p.username }}<span v-if="!p.connected"> (disconnected)</span>
        </li>
      </ul>
      <button type="button" class="start" @click="start">Start quiz</button>
    </section>

    <section v-else-if="store.phase === 'in_progress'" class="in-progress">
      <QuestionCard />
      <LeaderboardPanel />
    </section>

    <section v-else-if="store.phase === 'finished'" class="finished">
      <h2>Final results</h2>
      <LeaderboardPanel title="Final standings" />
    </section>
  </div>
</template>

<style scoped>
.quiz-room {
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1.5rem;
  display: grid;
  gap: 1.5rem;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.leave {
  padding: 0.4rem 0.8rem;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: transparent;
  cursor: pointer;
}
.participants {
  list-style: none;
  padding: 0;
  display: grid;
  gap: 0.4rem;
  margin: 1rem 0;
}
.participants .offline {
  opacity: 0.5;
}
.start {
  padding: 0.7rem 1.2rem;
  border-radius: 8px;
  border: none;
  background: hsla(160, 100%, 37%, 1);
  color: white;
  font-weight: 700;
  cursor: pointer;
}
.in-progress {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 1.5rem;
  align-items: start;
}
@media (max-width: 720px) {
  .in-progress {
    grid-template-columns: 1fr;
  }
}
.error {
  color: #cf222e;
  font-weight: 600;
}
</style>
