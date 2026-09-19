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
  <div class="join-view">
    <h1>ELSA Real-Time Quiz</h1>
    <p class="subtitle">Enter a quiz room to join, then wait for it to start.</p>

    <form @submit.prevent="onSubmit">
      <label>
        Quiz ID
        <input v-model="quizId" type="text" required placeholder="e.g. demo-quiz" />
      </label>
      <label>
        Your name
        <input v-model="username" type="text" required maxlength="24" placeholder="e.g. alice" />
      </label>
      <button type="submit" :disabled="store.connectionStatus === 'connecting'">Join quiz</button>
    </form>

    <ConnectionStatus />
    <p v-if="store.errorMessage" class="error">{{ store.errorMessage }}</p>
  </div>
</template>

<style scoped>
.join-view {
  max-width: 420px;
  margin: 3rem auto;
  padding: 2rem;
  border-radius: 16px;
  background: var(--color-background-soft);
  display: grid;
  gap: 1rem;
  text-align: center;
}
.subtitle {
  opacity: 0.75;
  margin-top: -0.5rem;
}
form {
  display: grid;
  gap: 0.9rem;
  text-align: left;
}
label {
  display: grid;
  gap: 0.35rem;
  font-weight: 600;
}
input {
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: var(--color-background);
  font-size: 1rem;
}
button {
  padding: 0.7rem 1rem;
  border-radius: 8px;
  border: none;
  background: hsla(160, 100%, 37%, 1);
  color: white;
  font-weight: 700;
  cursor: pointer;
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error {
  color: #cf222e;
  font-weight: 600;
}
</style>
