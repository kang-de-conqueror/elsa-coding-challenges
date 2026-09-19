<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useQuizStore } from '@/stores/quiz'
import { useQuizSocket } from '@/composables/useQuizSocket'

const store = useQuizStore()
const { submitAnswer } = useQuizSocket()

const selectedIndex = ref<number | null>(null)
const remainingMs = ref(0)
let tickHandle: ReturnType<typeof setInterval> | null = null

function tick(): void {
  remainingMs.value = store.questionDeadline ? Math.max(0, store.questionDeadline - Date.now()) : 0
}

onMounted(() => {
  tick()
  tickHandle = setInterval(tick, 100)
})
onBeforeUnmount(() => {
  if (tickHandle) clearInterval(tickHandle)
})

watch(
  () => store.currentQuestion?.question_id,
  () => {
    selectedIndex.value = null
  },
)

const remainingSeconds = computed(() => Math.ceil(remainingMs.value / 1000))
const progressPct = computed(() => {
  if (!store.currentQuestion) return 0
  return Math.max(0, Math.min(100, (remainingMs.value / store.currentQuestion.duration_ms) * 100))
})

function choose(index: number): void {
  if (!store.currentQuestion || store.hasAnsweredCurrentQuestion || remainingMs.value <= 0) return
  selectedIndex.value = index
  submitAnswer(store.currentQuestion.question_id, index)
}
</script>

<template>
  <div v-if="store.currentQuestion" class="question-card">
    <div class="meta">
      <span>Question {{ store.currentQuestion.index + 1 }} / {{ store.currentQuestion.total }}</span>
      <span class="timer">{{ remainingSeconds }}s</span>
    </div>
    <div class="progress-track">
      <div class="progress-fill" :style="{ width: progressPct + '%' }" />
    </div>
    <h2>{{ store.currentQuestion.text }}</h2>
    <ul class="choices">
      <li v-for="(choice, index) in store.currentQuestion.choices" :key="index">
        <button
          type="button"
          class="choice"
          :class="{ selected: selectedIndex === index }"
          :disabled="store.hasAnsweredCurrentQuestion || remainingMs <= 0"
          @click="choose(index)"
        >
          {{ choice }}
        </button>
      </li>
    </ul>
    <p v-if="store.lastAnswer && store.lastAnswer.question_id === store.currentQuestion.question_id" class="feedback" :class="{ correct: store.lastAnswer.correct }">
      {{ store.lastAnswer.correct ? `Correct! +${store.lastAnswer.points_awarded} points` : 'Incorrect' }}
    </p>
    <p v-else-if="store.hasAnsweredCurrentQuestion" class="feedback">Answer submitted, waiting for result…</p>
  </div>
</template>

<style scoped>
.question-card {
  padding: 1.5rem;
  border-radius: 12px;
  background: var(--color-background-soft);
  max-width: 560px;
}
.meta {
  display: flex;
  justify-content: space-between;
  font-weight: 600;
  margin-bottom: 0.5rem;
}
.timer {
  font-variant-numeric: tabular-nums;
}
.progress-track {
  height: 6px;
  border-radius: 999px;
  background: var(--color-background-mute);
  overflow: hidden;
  margin-bottom: 1rem;
}
.progress-fill {
  height: 100%;
  background: hsla(160, 100%, 37%, 1);
  transition: width 0.1s linear;
}
.choices {
  list-style: none;
  display: grid;
  gap: 0.6rem;
  padding: 0;
  margin: 1rem 0 0;
}
.choice {
  width: 100%;
  text-align: left;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: var(--color-background);
  cursor: pointer;
  font-size: 1rem;
}
.choice:hover:not(:disabled) {
  border-color: hsla(160, 100%, 37%, 1);
}
.choice.selected {
  border-color: hsla(160, 100%, 37%, 1);
  background: hsla(160, 100%, 37%, 0.12);
}
.choice:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}
.feedback {
  margin-top: 1rem;
  font-weight: 600;
  color: #cf222e;
}
.feedback.correct {
  color: #1a7f37;
}
</style>
