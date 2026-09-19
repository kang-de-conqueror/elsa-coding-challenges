<script setup lang="ts">
import { onMounted } from 'vue'
import { useQuizStore } from '@/stores/quiz'
import { useQuizSocket } from '@/composables/useQuizSocket'
import JoinView from '@/views/JoinView.vue'
import QuizRoomView from '@/views/QuizRoomView.vue'

const store = useQuizStore()
const { tryRejoin } = useQuizSocket()

// If the tab was reloaded mid-quiz, resume the previous session for the
// last-joined quiz id instead of showing an empty join form.
onMounted(() => {
  const params = new URLSearchParams(window.location.search)
  const quizIdFromUrl = params.get('quiz')
  if (quizIdFromUrl) {
    tryRejoin(quizIdFromUrl)
  }
})
</script>

<template>
  <JoinView v-if="store.phase === 'not_joined'" />
  <QuizRoomView v-else />
</template>
