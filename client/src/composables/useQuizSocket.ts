import { useQuizStore } from '@/stores/quiz'
import { PROTOCOL_VERSION, type ClientMessage, type ServerMessage } from '@/types/protocol'

// Module-level (not inside the composable function) so the connection and
// its timers are a true singleton across the app's lifetime, regardless of
// how many components call useQuizSocket().
let ws: WebSocket | null = null
let reconnectAttempt = 0
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let heartbeatTimer: ReturnType<typeof setInterval> | null = null
let manuallyClosed = false
let pendingUsername = ''

const SESSION_STORAGE_KEY = 'elsa-quiz-session'
const HEARTBEAT_INTERVAL_MS = 20_000
const MAX_RECONNECT_DELAY_MS = 15_000

function wsBaseUrl(): string {
  const configured = import.meta.env.VITE_WS_BASE_URL as string | undefined
  if (configured) return configured
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${window.location.hostname}:8000`
}

function saveSession(quizId: string, userId: string): void {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ quizId, userId }))
  } catch {
    // Best-effort only: a private-browsing tab or blocked storage just means
    // rejoin-after-disconnect won't restore the session. Not fatal.
  }
}

function loadSession(quizId: string): { userId: string } | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as { quizId?: unknown; userId?: unknown }
    if (parsed.quizId === quizId && typeof parsed.userId === 'string') {
      return { userId: parsed.userId }
    }
  } catch {
    // Corrupted/blocked storage: fall through to "no saved session".
  }
  return null
}

function clearSession(): void {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY)
  } catch {
    // Nothing to do if storage is unavailable.
  }
}

export function useQuizSocket() {
  const store = useQuizStore()

  function send(message: ClientMessage): void {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
    }
  }

  function handleMessage(message: ServerMessage, quizId: string): void {
    switch (message.type) {
      case 'joined':
        store.setJoined(message.quiz_id, message.user_id, message.username, message.state)
        saveSession(quizId, message.user_id)
        break
      case 'participant_update':
        store.setParticipants(message.participants)
        break
      case 'question':
        store.setQuestion(message)
        break
      case 'score_update':
        store.recordAnswer(message)
        break
      case 'leaderboard':
        store.setLeaderboard(message.standings)
        break
      case 'quiz_end':
        store.setFinished(message.final_standings)
        break
      case 'error':
        store.setError(message.message)
        break
      case 'pong':
        break
    }
  }

  function scheduleReconnect(quizId: string): void {
    reconnectAttempt += 1
    const delay = Math.min(1000 * 2 ** reconnectAttempt, MAX_RECONNECT_DELAY_MS)
    store.setConnectionStatus('reconnecting')
    reconnectTimer = setTimeout(() => connect(quizId), delay)
  }

  function connect(quizId: string): void {
    manuallyClosed = false
    store.quizId = quizId
    store.setConnectionStatus(reconnectAttempt > 0 ? 'reconnecting' : 'connecting')

    const socket = new WebSocket(`${wsBaseUrl()}/ws/${encodeURIComponent(quizId)}`)
    ws = socket

    socket.onopen = () => {
      reconnectAttempt = 0
      store.setConnectionStatus('open')
      const existing = loadSession(quizId)
      if (existing) {
        send({ v: PROTOCOL_VERSION, type: 'rejoin', quiz_id: quizId, user_id: existing.userId })
      } else if (pendingUsername) {
        send({ v: PROTOCOL_VERSION, type: 'join', quiz_id: quizId, username: pendingUsername })
      }
      heartbeatTimer = setInterval(() => send({ v: PROTOCOL_VERSION, type: 'ping' }), HEARTBEAT_INTERVAL_MS)
    }

    socket.onmessage = (event: MessageEvent<string>) => {
      handleMessage(JSON.parse(event.data) as ServerMessage, quizId)
    }

    socket.onclose = () => {
      store.setConnectionStatus('closed')
      if (heartbeatTimer) clearInterval(heartbeatTimer)
      if (!manuallyClosed) scheduleReconnect(quizId)
    }

    socket.onerror = () => {
      socket.close()
    }
  }

  function join(quizId: string, username: string): void {
    pendingUsername = username
    connect(quizId)
  }

  /** Attempt to resume a previously joined session for this quiz id (e.g. on page reload). */
  function tryRejoin(quizId: string): boolean {
    if (!loadSession(quizId)) return false
    connect(quizId)
    return true
  }

  function start(): void {
    send({ v: PROTOCOL_VERSION, type: 'start', quiz_id: store.quizId })
  }

  function submitAnswer(questionId: string, choiceIndex: number): void {
    send({
      v: PROTOCOL_VERSION,
      type: 'answer',
      request_id: crypto.randomUUID(),
      question_id: questionId,
      choice_index: choiceIndex,
    })
  }

  function leave(): void {
    manuallyClosed = true
    clearSession()
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (heartbeatTimer) clearInterval(heartbeatTimer)
    ws?.close()
    ws = null
    reconnectAttempt = 0
    store.reset()
  }

  return { join, tryRejoin, start, submitAnswer, leave }
}
