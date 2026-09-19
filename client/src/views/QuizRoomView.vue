<script setup lang="ts">
import { useQuizStore } from '@/stores/quiz'
import { useQuizSocket } from '@/composables/useQuizSocket'
import ConnectionStatus from '@/components/ConnectionStatus.vue'
import ScoreBadge from '@/components/ScoreBadge.vue'
import QuestionCard from '@/components/QuestionCard.vue'
import LeaderboardPanel from '@/components/LeaderboardPanel.vue'
import PodiumBoard from '@/components/PodiumBoard.vue'
import UserAvatar from '@/components/UserAvatar.vue'

const store = useQuizStore()
const { start, leave } = useQuizSocket()
</script>

<template>
  <div class="quiz-room">
    <header class="bar">
      <div class="left">
        <span class="logo" aria-hidden="true">E</span>
        <div class="room">
          <span class="room-label">Room</span>
          <strong class="room-code">{{ store.quizId }}</strong>
        </div>
        <ConnectionStatus />
      </div>
      <div class="right">
        <ScoreBadge v-if="store.phase !== 'lobby'" />
        <button type="button" class="btn btn-ghost leave" @click="leave">Leave</button>
      </div>
    </header>

    <p v-if="store.errorMessage" class="alert" role="alert">{{ store.errorMessage }}</p>

    <section v-if="store.phase === 'lobby'" class="lobby card">
      <div class="pulse" aria-hidden="true">⏳</div>
      <h2>Waiting for players…</h2>
      <p class="sub">
        Share the room code <strong>{{ store.quizId }}</strong> with your friends. Anyone in the room can start the
        quiz.
      </p>
      <ul class="participants">
        <li v-for="p in store.participants" :key="p.user_id" :class="{ offline: !p.connected }">
          <UserAvatar :name="p.username" :size="30" />
          <span class="pname">{{ p.username }}</span>
          <span v-if="p.user_id === store.userId" class="tag">You</span>
          <span v-if="!p.connected" class="tag off">offline</span>
        </li>
      </ul>
      <button type="button" class="btn btn-primary start" @click="start">Start quiz</button>
      <p class="count">{{ store.participants.length }} player{{ store.participants.length === 1 ? '' : 's' }} in the room</p>
    </section>

    <section v-else-if="store.phase === 'in_progress'" class="in-progress">
      <QuestionCard />
      <LeaderboardPanel />
    </section>

    <section v-else-if="store.phase === 'finished'" class="finished">
      <div class="card results">
        <h2>Final results</h2>
        <p class="sub">Great effort! Here is how everyone finished.</p>
        <PodiumBoard />
      </div>
      <div class="side">
        <LeaderboardPanel title="Final standings" :live="false" />
        <button type="button" class="btn btn-primary again" @click="leave">Play again</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.quiz-room {
  max-width: 1040px;
  margin: 0 auto;
  display: grid;
  gap: 1.25rem;
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.left,
.right {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  flex-wrap: wrap;
}
.logo {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  color: #fff;
  font-weight: 900;
  background: linear-gradient(135deg, var(--primary), var(--accent));
}
.room {
  display: grid;
  line-height: 1.1;
}
.room-label {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  font-weight: 700;
}
.room-code {
  font-size: 1.05rem;
}
.leave {
  padding: 0.55rem 1rem;
}
.lobby {
  padding: 2.25rem 1.5rem;
  display: grid;
  justify-items: center;
  gap: 0.9rem;
  text-align: center;
}
.pulse {
  font-size: 2.2rem;
  animation: bob 1.8s ease-in-out infinite;
}
.sub {
  margin: 0;
  color: var(--text-muted);
  max-width: 32rem;
}
.participants {
  list-style: none;
  padding: 0;
  margin: 0.4rem 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.6rem;
}
.participants li {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.9rem 0.35rem 0.4rem;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  font-weight: 700;
  animation: fade-in 0.3s ease both;
}
.participants li.offline {
  opacity: 0.5;
}
.tag {
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 0.7rem;
  font-weight: 800;
}
.tag.off {
  background: var(--danger-soft);
  color: var(--danger);
}
.start {
  font-size: 1.1rem;
  padding: 0.95rem 2.6rem;
}
.count {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}
.in-progress {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 1.25rem;
  align-items: start;
}
.finished {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 1.25rem;
  align-items: start;
}
.results {
  padding: 1.75rem 1.5rem 0;
  text-align: center;
  display: grid;
  gap: 0.4rem;
  overflow: hidden;
}
.side {
  display: grid;
  gap: 1rem;
}
.again {
  width: 100%;
}
@media (max-width: 860px) {
  .in-progress,
  .finished {
    grid-template-columns: 1fr;
  }
}
@keyframes bob {
  50% {
    transform: translateY(-6px);
  }
}
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}
</style>
