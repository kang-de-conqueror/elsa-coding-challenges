// WebSocket wire protocol (version 1).
//
// Mirrors server/app/schemas.py, the source of truth for the contract
// (see design/SYSTEM_DESIGN.md). Kept in sync by hand: for the scope of
// this challenge that manual step is an accepted trade-off (see
// design/adr/0001-websocket-vs-alternatives.md) rather than adding a
// codegen pipeline.

export const PROTOCOL_VERSION = 1

// ---- Client -> Server ----

export interface JoinMessage {
  v: number
  type: 'join'
  quiz_id: string
  username: string
}

export interface RejoinMessage {
  v: number
  type: 'rejoin'
  quiz_id: string
  user_id: string
}

export interface StartMessage {
  v: number
  type: 'start'
  quiz_id: string
}

export interface AnswerMessage {
  v: number
  type: 'answer'
  request_id: string
  question_id: string
  choice_index: number
}

export interface PingMessage {
  v: number
  type: 'ping'
}

export type ClientMessage = JoinMessage | RejoinMessage | StartMessage | AnswerMessage | PingMessage

// ---- Server -> Client ----

export interface ParticipantView {
  user_id: string
  username: string
  connected: boolean
}

export type QuizPhase = 'lobby' | 'in_progress' | 'finished'

export interface JoinedMessage {
  v: number
  type: 'joined'
  quiz_id: string
  user_id: string
  username: string
  state: QuizPhase
}

export interface ErrorMessage {
  v: number
  type: 'error'
  code: string
  message: string
}

export interface ParticipantUpdateMessage {
  v: number
  type: 'participant_update'
  participants: ParticipantView[]
}

export interface QuestionMessage {
  v: number
  type: 'question'
  question_id: string
  index: number
  total: number
  text: string
  choices: string[]
  duration_ms: number
  server_time_ms: number
}

export interface ScoreUpdateMessage {
  v: number
  type: 'score_update'
  user_id: string
  question_id: string
  correct: boolean
  points_awarded: number
  total_score: number
}

export interface LeaderboardEntry {
  rank: number
  user_id: string
  username: string
  score: number
}

export interface LeaderboardMessage {
  v: number
  type: 'leaderboard'
  standings: LeaderboardEntry[]
}

export interface QuizEndMessage {
  v: number
  type: 'quiz_end'
  final_standings: LeaderboardEntry[]
}

export interface PongMessage {
  v: number
  type: 'pong'
}

export type ServerMessage =
  | JoinedMessage
  | ErrorMessage
  | ParticipantUpdateMessage
  | QuestionMessage
  | ScoreUpdateMessage
  | LeaderboardMessage
  | QuizEndMessage
  | PongMessage
