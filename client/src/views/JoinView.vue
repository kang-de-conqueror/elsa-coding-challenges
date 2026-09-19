<script setup lang="ts">
import { ref } from 'vue'
import { useQuizStore } from '@/stores/quiz'
import { useQuizSocket } from '@/composables/useQuizSocket'
import ConnectionStatus from '@/components/ConnectionStatus.vue'

const store = useQuizStore()
const { join } = useQuizSocket()

const quizId = ref('demo-quiz')
const username = ref('')

function onSubmit(): void {
  if (!quizId.value.trim() || !username.value.trim()) return
  join(quizId.value.trim(), username.value.trim())
}
</script>

<template>
  <main class="join-view">
    <div class="brand">
      <span class="logo" aria-hidden="true">E</span>
      <span class="brand-name">ELSA Quiz</span>
    </div>

    <section class="hero">
      <h1>Ready to speak up?<br /><span class="gradient">Compete live.</span></h1>
      <p class="lead">
        Join a room with friends, answer vocabulary questions against the clock, and watch the leaderboard move in
        real time.
      </p>
      <ul class="perks" aria-label="Highlights">
        <li>⚡ Live scoring</li>
        <li>🏆 Real-time leaderboard</li>
        <li>⏱ Faster answers earn more</li>
      </ul>
    </section>

    <form class="card form" @submit.prevent="onSubmit">
      <h2>Join a quiz</h2>
      <label>
        Quiz ID
        <input v-model="quizId" type="text" required autocomplete="off" placeholder="e.g. demo-quiz" />
      </label>
      <label>
        Your name
        <input v-model="username" type="text" required maxlength="24" autocomplete="off" placeholder="e.g. Linh" />
      </label>
      <button class="btn btn-primary" type="submit" :disabled="store.connectionStatus === 'connecting'">Join quiz</button>
      <p v-if="store.errorMessage" class="alert" role="alert">{{ store.errorMessage }}</p>
      <div class="foot"><ConnectionStatus /></div>
    </form>
  </main>
</template>

<style scoped>
.join-view {
  max-width: 1040px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  grid-template-areas:
    'brand brand'
    'hero form';
  gap: 2rem 3rem;
  align-items: center;
  min-height: calc(100vh - 4.5rem);
  align-content: center;
}
.brand {
  grid-area: brand;
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.logo {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  color: #fff;
  font-weight: 900;
  font-size: 1.3rem;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  box-shadow: 0 6px 16px rgba(43, 27, 147, 0.3);
}
.brand-name {
  font-weight: 800;
  font-size: 1.2rem;
  color: var(--primary);
}
.hero {
  grid-area: hero;
  display: grid;
  gap: 1.1rem;
}
h1 {
  font-size: clamp(2.2rem, 5vw, 3.4rem);
  font-weight: 900;
  letter-spacing: -0.03em;
}
.gradient {
  background: linear-gradient(90deg, var(--primary), var(--accent));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.lead {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-muted);
  max-width: 34rem;
}
.perks {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}
.perks li {
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
  font-weight: 600;
  font-size: 0.88rem;
}
.form {
  grid-area: form;
  padding: 2rem;
  display: grid;
  gap: 1.1rem;
}
.form h2 {
  font-size: 1.4rem;
}
label {
  display: grid;
  gap: 0.4rem;
  font-weight: 700;
  font-size: 0.9rem;
}
input {
  padding: 0.8rem 0.95rem;
  border-radius: var(--radius-sm);
  border: 2px solid var(--border);
  background: var(--surface-2);
  font-size: 1rem;
  font-weight: 500;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--surface);
}
.foot {
  display: flex;
  justify-content: center;
}
@media (max-width: 860px) {
  .join-view {
    grid-template-columns: 1fr;
    grid-template-areas:
      'brand'
      'hero'
      'form';
    gap: 1.5rem;
  }
}
</style>
