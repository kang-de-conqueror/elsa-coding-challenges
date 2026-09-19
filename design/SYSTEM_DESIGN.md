# System Design: ELSA Real-Time Vocabulary Quiz

## 1. Overview

Users join a quiz session with a shared quiz ID, answer multiple-choice vocabulary questions, and see scores and a leaderboard update live for every participant in the room. This document covers the full system design (Part 1 of the challenge) and describes what was actually implemented as the "core real-time component" (Part 2): a full-stack slice — a FastAPI/WebSocket server and a Vue 3 client — with the question bank mocked (static in-memory data) rather than backed by a real content service.

## 2. Architecture

```
┌──────────────┐        WebSocket (wss)        ┌───────────────────────────────┐
│  Vue 3 client │ ─────────────────────────────▶│      FastAPI application       │
│ (per browser  │◀───────────────────────────── │                                 │
│    tab/user)  │      JSON message protocol    │  ┌───────────────────────────┐  │
└──────────────┘                                │  │   WebSocket endpoint       │  │
                                                 │  │   /ws/{quiz_id}            │  │
                                                 │  └─────────────┬──────────────┘  │
                                                 │                │ dispatch        │
                                                 │  ┌─────────────▼──────────────┐  │
                                                 │  │   ConnectionManager        │  │
                                                 │  │   (registry, broadcast,    │  │
                                                 │  │    rate limit, idle reap)  │  │
                                                 │  └─────────────┬──────────────┘  │
                                                 │                │                 │
                                                 │  ┌─────────────▼──────────────┐  │
                                                 │  │   QuizSession state machine │  │
                                                 │  │   (per quiz_id, own lock)   │  │
                                                 │  │   + scoring/leaderboard     │  │
                                                 │  └─────────────┬──────────────┘  │
                                                 │                │                 │
                                                 │  ┌─────────────▼──────────────┐  │
                                                 │  │  InMemorySessionStore       │  │
                                                 │  │  (dict[quiz_id -> session]) │  │
                                                 │  └─────────────────────────────┘  │
                                                 │                                 │
                                                 │  /healthz   /metrics (Prometheus)│
                                                 └───────────────────────────────┘
```

A production deployment of this architecture beyond one process would add a load balancer in front of multiple server instances and a Redis layer for shared state and cross-instance Pub/Sub fan-out — see ADR 0002 for why that is documented, not implemented, for this challenge.

## 3. Components

- **Vue 3 client** (`client/`): one WebSocket connection per browser tab. `useQuizSocket.ts` owns the connection lifecycle (connect, reconnect with exponential backoff, heartbeat ping, rejoin from a saved per-tab session). A Pinia store (`stores/quiz.ts`) holds all quiz state as the single source of truth for the UI; components (`QuestionCard`, `LeaderboardPanel`, `ScoreBadge`, `ConnectionStatus`) are pure renderers of that state.
- **WebSocket endpoint** (`server/app/main.py`): the composition root. Accepts a connection per `(quiz_id)`, parses every inbound message against the versioned Pydantic schema (`schemas.py`), and dispatches to one of four handlers (join, rejoin, start, answer). Never trusts client-supplied score or timing data (see ADR 0003).
- **ConnectionManager** (`connection_manager.py`): the registry of live sockets per quiz room, the broadcast fan-out, per-connection answer rate limiting (token bucket), and idle-connection reaping (a connection silent for 60s is force-closed — catches a half-open connection, e.g. a laptop going to sleep, that a clean-disconnect handler alone would never see).
- **QuizSession state machine** (`quiz.py`): owns one quiz room's participants, current question, and scores, behind its own `asyncio.Lock`. State machine: `LOBBY -> IN_PROGRESS -> FINISHED`. Answer submission is idempotent by client-generated `request_id`, so a client retry after a dropped ack can never double-score.
- **Scoring/ranking** (`scoring.py`): pure functions, no I/O, no asyncio — see ADR 0003 for the formula and tie-break rule.
- **SessionStore** (`session_store.py`): a narrow interface with one implementation (`InMemorySessionStore`) today; see ADR 0002 for the documented Redis-backed alternative.
- **Observability** (`observability.py`): structured JSON logs correlated by `quiz_id`/`user_id`, and Prometheus metrics (`active_connections`, `active_sessions`, `answers_processed_total`, `broadcast_latency_seconds`, `messages_rejected_total`) exposed at `/metrics`.
- **Mocked**: the question bank (`mock_question_bank()` — a static in-memory list) and authentication (a participant is just a chosen display name, no login). These are the explicit "mock the rest" cut described in the challenge brief.

## 4. Data flow: join to leaderboard update

1. **Join**: client opens `ws://.../ws/{quiz_id}` and sends `{type: "join", quiz_id, username}`. The server creates the quiz room on first reference (`SessionStore.get_or_create`), adds the participant to `QuizSession.participants` under the session's lock, registers the socket in `ConnectionManager`, replies `joined` to the caller, and broadcasts `participant_update` to everyone already in the room.
2. **Start**: any joined participant sends `{type: "start"}` (kept deliberately simple — no separate "host" role — for a challenge-scope demo). The server transitions the session to `IN_PROGRESS` and spawns one background task (`_run_quiz`) that owns the question timer for that room: broadcast `question` -> sleep for `duration_ms` -> broadcast the leaderboard -> advance to the next question -> repeat, finishing with `quiz_end`.
3. **Answer**: client sends `{type: "answer", request_id, question_id, choice_index}`. The server computes elapsed time from its own `time.monotonic()` clock (never from anything the client sent), scores the answer (`scoring.calculate_points`), sends a private `score_update` ack to that client, and schedules a leaderboard broadcast (see "Capacity" below for why this is *scheduled*, not immediate).
4. **Leaderboard update**: every currently-connected client in the room receives `leaderboard` with the full ranked standings. The Vue store replaces its `leaderboard` array; `LeaderboardPanel.vue` re-renders the ordered list reactively — no per-participant diffing needed at this scale.
5. **Disconnect/rejoin**: on a clean disconnect, the server marks the participant `connected: false` and broadcasts `participant_update`; the client's saved `{quiz_id, user_id}` (sessionStorage, so two tabs of one browser stay two different users) lets `tryRejoin` restore the exact same participant (and score) on reconnect via `{type: "rejoin"}`.

## 5. Technology choices

| Concern | Choice | Why |
|---|---|---|
| Real-time transport | WebSocket (FastAPI native) | See ADR 0001 |
| Server framework | FastAPI + `uvicorn[standard]` | Native ASGI WebSocket support, Pydantic integration for a strongly-typed wire protocol, minimal boilerplate |
| Message validation | Pydantic v2, discriminated union on `type` | Malformed/unexpected input always becomes a typed `error` reply, never an unhandled exception |
| Session state | In-memory, per-room `asyncio.Lock` | See ADR 0002 |
| Metrics | `prometheus-client`, `/metrics` endpoint | Standard scrape format, zero extra infrastructure to demo |
| Client framework | Vue 3 + `<script setup>` + TypeScript | Small, reactive, well-suited to a state-driven single-view app; Pinia gives one clear source of truth for the WebSocket-driven state |
| Client state | Pinia | Official Vue state library; plays well with the composable-owned WebSocket singleton |
| Server tooling | ruff (lint), mypy --strict (types), pytest | Fast, zero-config-heavy, catches an entire class of bugs (untyped `Any` leaking through the protocol) before runtime |
| Client tooling | ESLint + oxlint, vue-tsc, Vitest, Playwright (browser e2e) | Matches the create-vue "recommended" toolchain; consistent with the server's lint/type-check/test three-step |
| Containerization | Docker + Compose | One-command (`docker compose up`) reviewer demo without a local Python/Node setup |

## 6. Non-functional requirements

- **Latency**: p95 broadcast/ack latency under 150ms on localhost, for realistic (non-synchronized) participant load — see measured numbers below.
- **Consistency**: strong, within one quiz room, within one process (see ADR 0003). No cross-instance consistency claim (see ADR 0002).
- **Durability**: none. A server restart loses all in-flight quizzes. Acceptable for short-lived quiz sessions; explicitly out of scope to fix here.
- **Correctness under network jitter**: scoring always uses the server's own receive timestamp; a client cannot lie about how fast it answered.
- **Reliability**: clean disconnects are caught immediately (`WebSocketDisconnect`); half-open connections are caught within `idle_timeout_seconds` (default 60s) by a periodic reaper.

## 7. Capacity: what was measured, not assumed

`server/scripts/load_test.py` simulates N concurrent WebSocket clients joining one room and answering a question, and reports (a) each client's own answer-ack round-trip time (self-referential — no clock sync between client and server needed) and (b) the spread between the first and last client to receive one leaderboard broadcast. It is a manual script (not run in CI); the numbers below are from this dev machine (Windows, single `uvicorn` worker, no `--workers`), run against `localhost`.

**First run surfaced a real bug.** The original implementation broadcast the *full* leaderboard to *every* participant after *every single* answer. With 300 clients all answering within the same short window (an artificial, fully-synchronized worst case — see below), that is O(N²) sequential `send` calls on one event loop: 300 answers x 300 sends = up to 90,000 sequential awaits. Measured: mean answer-ack latency ~5s, p50 ~6.0s. This was root-caused (not guessed at) by re-reading the broadcast call sites after seeing the anomalous latency, fixed by debouncing same-room leaderboard broadcasts (`main.py::_schedule_leaderboard_broadcast`, 150ms coalescing window — a burst of answers within the window collapses into one broadcast reflecting the latest state), and re-measured:

| Clients | Pattern | p50 ack RTT | p95 ack RTT | Leaderboard fan-out spread |
|---|---|---|---|---|
| 50 | fully synchronized (worst case) | 2.2ms | 17.5ms | 6.4ms |
| 100 | fully synchronized (worst case) | 12.9ms | 37.9ms | 22.2ms |
| 100 | staggered over 300ms (human-like) | 2.3ms | 383.8ms | 125.3ms |
| 150 | fully synchronized (worst case) | 572.6ms | 1002.5ms | 25.2ms |
| 200 | fully synchronized (worst case) | 675.6ms | 2380.2ms | 1085.1ms |
| 300 | fully synchronized, **before** the debounce fix | 5999.5ms | 8266.9ms | 1481.2ms |
| 300 | fully synchronized, **after** the debounce fix | 916.4ms | 8838.7ms | 264.8ms |

Reading this honestly: the debounce fix cut the leaderboard fan-out spread by ~5.6x at 300 clients and cut median ack latency by ~6.5x, but a *fully-synchronized* burst of 300+ answers on a *single process* still has a long tail, because 300 independent `submit_answer` calls genuinely have to be processed one at a time by one event loop (the per-session lock that guarantees correctness also serializes the work). The knee is between 100 and 150 synchronized clients on this dev machine. Two things matter for interpreting this:

1. **Real users do not answer in perfect lockstep.** Human reaction time naturally spreads answers over hundreds of milliseconds to a few seconds. The one successful staggered measurement (100 clients, 300ms jitter) shows p50 staying near-instant even though the tail is wider than the unrealistic synchronized case.
2. **This is exactly the motivation for ADR 0002.** A single process has a hard ceiling; the documented (not implemented) path past it is sharding quiz rooms across multiple instances behind Redis Pub/Sub, so no single instance ever has to serialize a 300-way synchronized burst alone.

**Revised concurrency target** (superseding an earlier, pre-measurement guess of 300-500): **this single-process implementation comfortably handles on the order of 100 concurrently-answering participants per room** with realistic (non-synchronized) human answer timing, based on measured data rather than assumption. Scaling past that on one machine is a matter of moving the broadcast fan-out off the request path entirely (e.g. a dedicated broadcaster task per room, or the Redis Pub/Sub path in ADR 0002) — not implemented here, but now backed by a measured, understood bottleneck rather than a guess.

## 8. Reliability, security, maintainability, observability

- **Reliability**: idempotent answer submission (one scored answer per participant per question; a retry or second click replays the original result instead of scoring again), rejoin that resyncs the client (running question with the time actually left, its own earlier result, standings, or the final result), idle-connection reaping, finished quizzes freed after a 10 minute grace period, socket-aware cleanup (a stale socket can never evict the one that replaced it), graceful per-connection error handling (a malformed message or a broken socket never crashes the room for other participants — see `connection_manager.py::_safe_send`).
- **Security**: all inbound messages are Pydantic-validated (length-bounded strings, bounded `choice_index`); score/timing is always server-computed; per-connection rate limiting on answer submission (token bucket, 5 tokens / 5s) guards against a scripted spam client; Vue's default output escaping means a hostile username cannot inject markup into the leaderboard.
- **Maintainability**: `ruff` + `mypy --strict` + `pytest` gate the server in CI; `eslint`/`oxlint` + `vue-tsc` + a production build gate the client. The state machine, scoring, and connection management are separated into small, independently-testable modules (see the file list in the root README).
- **Observability**: structured JSON logs with `quiz_id`/`user_id` context on every state-changing event; `/metrics` exposes the counters/histograms in section 6 in Prometheus format, so `active_connections`, `active_sessions`, `answers_processed_total`, and `broadcast_latency_seconds` are all things an operator could graph and alert on today, not just a paragraph of intent.

## 9. Out of scope (and why)

- **Redis-backed session store / multi-instance horizontal scaling** — documented in ADR 0002; not implemented because it is out of proportion to a challenge that asks for one real-time component with the rest mocked, and because a half-implemented distributed system is a worse signal than a correct single-process one with an honest scaling story.
- **Real authentication** — a participant is a freely-chosen display name; no login, no accounts. Out of scope for a quiz demo; would be the first thing added for a real product.
- **Durability past a server restart** — quiz state is in-memory only. Acceptable for short-lived quiz sessions; would move to Redis alongside the horizontal-scaling work in ADR 0002.
- **Cross-browser / visual regression testing** — the client has Vitest store tests and one Playwright flow (`client/e2e/quiz-flow.mjs`, real Chrome/Edge, two tabs) covering join, live scoring, leaderboard, reload-and-resume and the final screen; it does not cover other browsers or pixel-level regressions.
