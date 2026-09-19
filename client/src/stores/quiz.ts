import { defineStore } from 'pinia'
import type {
  LeaderboardEntry,
  ParticipantView,
  QuestionMessage,
  QuizPhase,
  ScoreUpdateMessage,
} from '@/types/protocol'

export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'

interface QuizState {
  connectionStatus: ConnectionStatus
  quizId: string
  userId: string
  username: string
  phase: QuizPhase | 'not_joined'
  participants: ParticipantView[]
  currentQuestion: QuestionMessage | null
  questionDeadline: number | null // Date.now()-based deadline computed on receipt, for the countdown UI
  lastAnswer: ScoreUpdateMessage | null
  answeredQuestionIds: Set<string>
  leaderboard: LeaderboardEntry[]
  finalStandings: LeaderboardEntry[] | null
  errorMessage: string | null
}

export const useQuizStore = defineStore('quiz', {
  state: (): QuizState => ({
    connectionStatus: 'idle',
    quizId: '',
    userId: '',
    username: '',
    phase: 'not_joined',
    participants: [],
    currentQuestion: null,
    questionDeadline: null,
    lastAnswer: null,
    answeredQuestionIds: new Set(),
    leaderboard: [],
    finalStandings: null,
    errorMessage: null,
  }),
  getters: {
    myRank(state): number | null {
      const entry = state.leaderboard.find((e) => e.user_id === state.userId)
      return entry ? entry.rank : null
    },
    myScore(state): number {
      const entry = state.leaderboard.find((e) => e.user_id === state.userId)
      return entry ? entry.score : 0
    },
    hasAnsweredCurrentQuestion(state): boolean {
      return state.currentQuestion !== null && state.answeredQuestionIds.has(state.currentQuestion.question_id)
    },
  },
  actions: {
    setConnectionStatus(status: ConnectionStatus) {
      this.connectionStatus = status
    },
    setJoined(quizId: string, userId: string, username: string, phase: QuizPhase) {
      this.quizId = quizId
      this.userId = userId
      this.username = username
      this.phase = phase
      this.errorMessage = null
    },
    setParticipants(participants: ParticipantView[]) {
      this.participants = participants
    },
    setQuestion(question: QuestionMessage) {
      this.currentQuestion = question
      this.questionDeadline = Date.now() + question.duration_ms
      this.phase = 'in_progress'
      this.lastAnswer = null
    },
    recordAnswer(ack: ScoreUpdateMessage) {
      if (ack.user_id === this.userId) {
        this.lastAnswer = ack
        this.answeredQuestionIds.add(ack.question_id)
      }
    },
    setLeaderboard(standings: LeaderboardEntry[]) {
      this.leaderboard = standings
    },
    setFinished(finalStandings: LeaderboardEntry[]) {
      this.finalStandings = finalStandings
      this.leaderboard = finalStandings
      this.phase = 'finished'
      this.currentQuestion = null
    },
    setError(message: string) {
      this.errorMessage = message
    },
    reset() {
      this.$reset()
    },
  },
})
