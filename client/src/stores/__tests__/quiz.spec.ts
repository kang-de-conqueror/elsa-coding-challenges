import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useQuizStore } from '../quiz'
import type { QuestionMessage, ScoreUpdateMessage } from '@/types/protocol'

const question: QuestionMessage = {
  v: 1,
  type: 'question',
  question_id: 'q1',
  index: 0,
  total: 2,
  text: 'Pick one',
  choices: ['a', 'b'],
  duration_ms: 10_000,
  server_time_ms: 0,
}

function ack(userId: string, overrides: Partial<ScoreUpdateMessage> = {}): ScoreUpdateMessage {
  return {
    v: 1,
    type: 'score_update',
    user_id: userId,
    question_id: 'q1',
    correct: true,
    points_awarded: 1200,
    total_score: 1200,
    ...overrides,
  }
}

describe('quiz store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts not joined with an empty leaderboard', () => {
    const store = useQuizStore()
    expect(store.phase).toBe('not_joined')
    expect(store.leaderboard).toEqual([])
    expect(store.myRank).toBeNull()
    expect(store.myScore).toBe(0)
  })

  it('derives my rank and score from the leaderboard', () => {
    const store = useQuizStore()
    store.setJoined('room', 'me', 'alice', 'lobby')
    store.setLeaderboard([
      { rank: 1, user_id: 'other', username: 'bob', score: 2000 },
      { rank: 2, user_id: 'me', username: 'alice', score: 1500 },
    ])
    expect(store.myRank).toBe(2)
    expect(store.myScore).toBe(1500)
  })

  it('moves to in_progress and sets a countdown deadline when a question arrives', () => {
    const store = useQuizStore()
    const before = Date.now()
    store.setQuestion(question)
    expect(store.phase).toBe('in_progress')
    expect(store.questionDeadline).toBeGreaterThanOrEqual(before + 10_000)
    expect(store.lastAnswer).toBeNull()
  })

  it('marks the current question answered only for my own acknowledgement', () => {
    const store = useQuizStore()
    store.setJoined('room', 'me', 'alice', 'in_progress')
    store.setQuestion(question)

    store.recordAnswer(ack('someone-else'))
    expect(store.hasAnsweredCurrentQuestion).toBe(false)

    store.recordAnswer(ack('me'))
    expect(store.hasAnsweredCurrentQuestion).toBe(true)
    expect(store.lastAnswer?.points_awarded).toBe(1200)
  })

  it('a new question clears the previous answer feedback', () => {
    const store = useQuizStore()
    store.setJoined('room', 'me', 'alice', 'in_progress')
    store.setQuestion(question)
    store.recordAnswer(ack('me'))

    store.setQuestion({ ...question, question_id: 'q2', index: 1 })

    expect(store.lastAnswer).toBeNull()
    expect(store.hasAnsweredCurrentQuestion).toBe(false)
  })

  it('finishing the quiz stores final standings and clears the question', () => {
    const store = useQuizStore()
    store.setQuestion(question)
    store.setFinished([{ rank: 1, user_id: 'me', username: 'alice', score: 900 }])

    expect(store.phase).toBe('finished')
    expect(store.currentQuestion).toBeNull()
    expect(store.leaderboard).toHaveLength(1)
  })

  it('reset returns to the initial state', () => {
    const store = useQuizStore()
    store.setJoined('room', 'me', 'alice', 'lobby')
    store.reset()
    expect(store.phase).toBe('not_joined')
    expect(store.userId).toBe('')
  })
})
