<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useQuizStore } from '@/stores/quiz'
import { useQuizSocket } from '@/composables/useQuizSocket'

const store = useQuizStore()
const { submitAnswer } = useQuizSocket()

const selectedIndex = ref<number | null>(null)
const remainingMs = ref(0)
let tickHandle: ReturnType<typeof setInterval> | null = null

const RING_RADIUS = 26
const RING_LENGTH = 2 * Math.PI * RING_RADIUS
const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

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
const fraction = computed(() => {
  if (!store.currentQuestion) return 0
  return Math.max(0, Math.min(1, remainingMs.value / store.currentQuestion.duration_ms))
})
const urgency = computed(() => (fraction.value > 0.5 ? 'calm' : fraction.value > 0.25 ? 'warn' : 'danger'))

const result = computed(() => {
  const ack = store.lastAnswer
  const question = store.currentQuestion
  return ack && question && ack.question_id === question.question_id ? ack : null
})

function choiceState(index: number): 'idle' | 'correct' | 'wrong' | 'selected' {
  if (selectedIndex.value !== index) return 'idle'
  if (!result.value) return 'selected'
  return result.value.correct ? 'correct' : 'wrong'
}

function choose(index: number): void {
  if (!store.currentQuestion || selectedIndex.value !== null || store.hasAnsweredCurrentQuestion) return
  if (remainingMs.value <= 0) return
  selectedIndex.value = index
  submitAnswer(store.currentQuestion.question_id, index)
}
</script>

<template>
  <div v-if="store.currentQuestion" class="question-card card">
    <div class="top">
      <span class="progress-pill">Question {{ store.currentQuestion.index + 1 }} / {{ store.currentQuestion.total }}</span>
      <div class="timer" :class="urgency" :aria-label="`${remainingSeconds} seconds left`">
        <svg viewBox="0 0 64 64" width="64" height="64" aria-hidden="true">
          <circle class="track" cx="32" cy="32" :r="RING_RADIUS" />
          <circle
            class="bar"
            cx="32"
            cy="32"
            :r="RING_RADIUS"
            :stroke-dasharray="RING_LENGTH"
            :stroke-dashoffset="RING_LENGTH * (1 - fraction)"
          />
        </svg>
        <span class="seconds">{{ remainingSeconds }}s</span>
      </div>
    </div>

    <h2 class="text">{{ store.currentQuestion.text }}</h2>

    <ul class="choices">
      <li v-for="(choice, index) in store.currentQuestion.choices" :key="index">
        <button
          type="button"
          class="choice"
          :class="choiceState(index)"
          :disabled="selectedIndex !== null || store.hasAnsweredCurrentQuestion || remainingMs <= 0"
          @click="choose(index)"
        >
          <span class="letter" aria-hidden="true">{{ LETTERS[index] }}</span>
          <span class="label">{{ choice }}</span>
        </button>
      </li>
    </ul>

    <p v-if="result" class="feedback" :class="result.correct ? 'good' : 'bad'" role="status">
      {{ result.correct ? `Correct! +${result.points_awarded} points` : 'Incorrect' }}
      <span class="hint">{{ result.correct ? 'Nice one — keep the streak going.' : "Don't worry, the next one is yours." }}</span>
    </p>
    <p v-else-if="store.hasAnsweredCurrentQuestion" class="feedback pending" role="status">
      Answer submitted, waiting for result…
    </p>
    <p v-else class="feedback idle">Pick an answer — faster answers earn bonus points.</p>
  </div>
</template>

<style scoped>
.question-card {
  padding: 1.5rem;
  display: grid;
  gap: 1.1rem;
}
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.progress-pill {
  padding: 0.3rem 0.85rem;
  border-radius: 999px;
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 700;
  font-size: 0.85rem;
}
.timer {
  position: relative;
  width: 64px;
  height: 64px;
}
.timer svg {
  transform: rotate(-90deg);
}
.timer circle {
  fill: none;
  stroke-width: 6;
}
.timer .track {
  stroke: var(--surface-2);
}
.timer .bar {
  stroke-linecap: round;
  transition:
    stroke-dashoffset 0.12s linear,
    stroke 0.3s ease;
}
.timer.calm .bar {
  stroke: var(--accent);
}
.timer.warn .bar {
  stroke: var(--warning);
}
.timer.danger .bar {
  stroke: var(--danger);
}
.seconds {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.timer.danger .seconds {
  color: var(--danger);
}
.text {
  font-size: clamp(1.25rem, 2.6vw, 1.7rem);
  font-weight: 800;
}
.choices {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
@media (max-width: 560px) {
  .choices {
    grid-template-columns: 1fr;
  }
}
.choice {
  width: 100%;
  min-height: 64px;
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.7rem 0.9rem;
  text-align: left;
  border-radius: var(--radius-sm);
  border: 2px solid var(--border);
  background: var(--surface);
  font-weight: 600;
  transition:
    transform 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}
.letter {
  flex: none;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 800;
}
.choice:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: var(--primary);
  box-shadow: var(--shadow);
}
.choice:disabled {
  cursor: default;
}
.choice:disabled.idle {
  opacity: 0.55;
}
.choice.selected {
  border-color: var(--primary);
  background: var(--primary-soft);
}
.choice.correct {
  border-color: var(--success);
  background: var(--success-soft);
}
.choice.correct .letter {
  background: var(--success);
  color: #fff;
}
.choice.wrong {
  border-color: var(--danger);
  background: var(--danger-soft);
}
.choice.wrong .letter {
  background: var(--danger);
  color: #fff;
}
.feedback {
  margin: 0;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-sm);
  font-weight: 700;
  display: grid;
  gap: 0.1rem;
}
.feedback .hint {
  font-size: 0.85rem;
  font-weight: 500;
  opacity: 0.85;
}
.feedback.good {
  background: var(--success-soft);
  color: var(--success);
}
.feedback.bad {
  background: var(--danger-soft);
  color: var(--danger);
}
.feedback.pending,
.feedback.idle {
  background: var(--surface-2);
  color: var(--text-muted);
  font-weight: 600;
}
</style>
