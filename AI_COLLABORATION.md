# AI Collaboration

**Tool**: Claude Code (Claude Sonnet 5, Anthropic), used interactively throughout both the design and implementation phases of this challenge — not applied retroactively to hand-written code.

This document describes where and how AI meaningfully shaped the design and code (not simple autocomplete), what was asked for, and — the part the challenge brief calls "crucial" — how each AI-assisted piece was actually verified rather than taken on faith.

## How the session was structured

The work started in Claude Code's plan mode: given only the challenge's GitHub repo URL, Claude Code was asked to pull the repo, read the brief, and produce an implementation plan before writing any code. Three things shaped that plan through direct instruction, not AI initiative:

1. Clarifying questions were asked back (rather than assumed) on genuinely ambiguous scope: which component to implement (server, client, or both — full-stack slice was chosen), tech stack (Python/FastAPI + Vue 3, matching prior project familiarity), and language for the plan itself.
2. After the first plan draft, the explicit instruction "plan and implement like a principal software engineer with 20 years of experience" was given. This materially changed the plan: it added non-functional requirements defined *before* coding, a protocol-first design (versioned message schema, idempotency, server-authoritative timestamps), ADRs for the three decisions most worth defending, a real (not just described) metrics endpoint, and a load-test script to *measure* rather than *assert* capacity claims.
3. Every code change below was reviewed in the same session — files were read back, lint/type-check/test output was inspected, and failures were fixed before moving on, rather than trusting a single generation pass.

## Design phase

**Task**: system architecture, WebSocket message protocol, scoring/tie-break rule, and the three ADRs.

**AI's role**: Claude Code proposed the initial architecture (FastAPI/WebSocket + Vue/Pinia, in-memory session store behind a narrow interface), the full message protocol (join/rejoin/start/answer/ping client-side; joined/error/participant_update/question/score_update/leaderboard/quiz_end/pong server-side), and the scoring formula (base points + time-remaining bonus, with a three-level tie-break: score, then cumulative response time, then join order).

**Verification**: the protocol was cross-checked for completeness against every UI state the client would need (lobby, in-progress, finished, disconnected/rejoining) before any server code was written, catching one gap early (a rejoining client needs the live state replayed, not just a confirmation — later strengthened in the review round below to also resend the running question, the user's own result and the standings). The scoring/tie-break design was validated after the fact with unit tests (`server/tests/test_scoring.py`) covering boundary cases (zero time remaining, full time remaining, negative/over-range clamping, all three tie-break levels) — see "Server implementation" below.

## Server implementation

**Task**: the FastAPI/WebSocket backend — `quiz.py` (state machine), `scoring.py`, `connection_manager.py`, `session_store.py`, `observability.py`, `main.py`, and the full test suite.

**AI's role**: Claude Code wrote all of the above from the agreed design, including the concurrency-safety approach (`asyncio.Lock` per quiz room) and the idempotent-answer design (one scored answer per participant per question; retries replay the original result).

**Verification** (concrete, not just "it looked right"):

- `ruff check` and `mypy --strict` were run after every file, and every finding was fixed before moving on — not deferred to a final pass. Two real strict-mode gaps were caught and fixed this way: an untyped `dict` parameter (`schemas.py::parse_client_message`) and several lines exceeding the configured line-length that would have failed CI.
- The full pytest suite (38 tests after the review round) was run repeatedly during development, including a targeted concurrency test (`test_concurrent_answers_from_many_participants_never_corrupt_state`) that fires 50 simultaneous `submit_answer` calls via `asyncio.gather` specifically to catch a lost-update bug if the per-session lock were ever removed or misapplied — this is a regression test for a class of bug, not just a happy-path check.
- The integration test (`test_integration_ws.py`) runs the *real* FastAPI app (not a mock) with three concurrent simulated WebSocket clients through a full join -> start -> answer -> quiz_end flow, asserting the final leaderboard ranking is correct.
- The server was actually started (`uvicorn app.main:app`) and hit with real HTTP/WebSocket traffic (`curl /healthz`, `curl /metrics`) to confirm it boots and serves correctly outside the test harness — catching issues a unit test alone wouldn't (e.g. the FastAPI `lifespan` wiring for the idle-connection reaper background task).
- **A load test caught a real bug that code review alone had missed.** `scripts/load_test.py` was written and run against the live server at increasing scale (50 -> 100 -> 150 -> 200 -> 300 simulated clients). The first 300-client run measured a mean answer-ack latency of ~5 seconds — nowhere near the <150ms target. Rather than accepting or hand-waving this, the broadcast code path was re-read, which revealed an O(N²) bug: the full leaderboard was being broadcast to all N participants after *every single* answer, so a synchronized burst of N answers costs N x N sequential sends. This was fixed with a 150ms debounce/coalescing window (`main.py::_schedule_leaderboard_broadcast`), and the *same* load test was re-run to confirm the fix: leaderboard fan-out spread dropped from 1481ms to 265ms and median ack latency dropped from ~6.0s to ~0.9s at 300 clients (full numbers and methodology in `design/SYSTEM_DESIGN.md`, section 7). The originally planned NFR ("300-500 concurrent participants") was revised downward to a measured, honest number after this data, rather than left as an unverified assumption.

## Client implementation

**Task**: the Vue 3/TypeScript/Pinia frontend — protocol types, the `useQuizSocket` composable (connection lifecycle, reconnect with backoff, heartbeat, rejoin-from-sessionStorage), the Pinia store, and all five components/views.

**AI's role**: Claude Code scaffolded the project (`npm create vue@latest`) and wrote all application code against the same protocol contract as the server.

**Verification**:

- `vue-tsc --build` (strict TypeScript project references) and `eslint`/`oxlint` were run and fixed to a clean state (one real issue caught: a single-word component name, `Leaderboard.vue`, violating the Vue style guide's multi-word component rule — renamed to `LeaderboardPanel.vue`).
- A production build (`vite build`) was run to confirm the app actually compiles and bundles, not just type-checks in isolation.
- A real browser test was added (`client/e2e/quiz-flow.mjs`, Playwright driving installed Edge/Chrome): two tabs join, play, answer right/wrong, watch the live leaderboard, reload one tab mid-question and resume, and reach the final screen with zero console errors. A screenshot of the final screen was also inspected by eye.

## Infrastructure and docs

**Task**: `pyproject.toml` (ruff/mypy/pytest config), `Dockerfile`s, `docker-compose.yml`, `.github/workflows/ci.yml`, the design document, ADRs, and this file.

**AI's role**: written directly by Claude Code, using the same lint/type-check/test commands locally as configured in CI, so CI is expected to reproduce local results rather than being an untested guess.

**Verification**: the Docker Compose health check depends on the same `/healthz` endpoint exercised manually above; the CI workflow runs the exact commands already verified locally in this session (`ruff check`, `mypy app`, `pytest -q`, `npm run lint`, `npm run type-check`, `npm run build`) rather than a different, untested command set — but the CI workflow itself has not been run against GitHub Actions as part of this session (no push was made), so it should be treated as "written and locally-equivalent-verified," not "confirmed green in CI."

## Honest summary of what is and isn't verified

**Verified in this session**: server correctness under concurrency (automated + load test), server API surface (manual + automated), the WebSocket protocol contract end-to-end (both server-side integration test and a client-shaped script), static analysis (lint + strict types) on both server and client, and that the client builds.

**Also verified**: the GitHub Actions workflow ran green on GitHub's runners (server and client jobs) after the push.

**Not verified**: browsers other than Chromium-based Edge/Chrome.

## Review round (engineering-manager style code review)

After the first implementation, the whole codebase was re-read as a reviewer would, and every finding was fixed with a regression test and its own commit rather than folded into feature commits. Findings:

1. **Stale socket evicted the live one.** After a rejoin, the old socket's cleanup removed the *new* socket from the room and marked the user offline. Cleanup is now socket-aware. Regression test: `test_stale_socket_closing_after_rejoin_does_not_evict_new_socket`. Mutation-checked: reverting the fix makes the test fail.
2. **Room id in the message body was trusted.** A client on `/ws/A` could send `join` for room B, leaking registrations and breaking lookups. The URL room is now authoritative; mismatches get `INVALID_MESSAGE`.
3. **Unjoined sockets could start quizzes; one socket could join repeatedly.** Now rejected (`UNKNOWN_USER` / `INVALID_MESSAGE`).
4. **Rejoin left the UI blank.** A reconnecting client missed every broadcast. The server now resyncs question (with remaining time), the user's own earlier result, standings, or the final result.
5. **A rejoin could lock the user out of the current question** (the score sync was treated as an answer). Fixed together with 4; duplicate answers now replay the original result instead of a misleading `Incorrect`.
6. **Sessions were never freed.** Finished quizzes are removed after a 10 minute grace period.
7. **Two tabs in one browser rejoined as the same user** because the session lived in `localStorage`. Now `sessionStorage`. Found by thinking through the two-tab demo, confirmed by the browser test.
8. **Client leaked a socket on re-join and could get trapped by a stale saved session.** Old sockets are closed with handlers detached; an unknown saved session falls back to a fresh join. Double-clicking an answer is blocked locally.
9. **Test hygiene.** A timing-sensitive assertion in the 50-way concurrency test was made exact per participant; `pytest-timeout` was added because a regression previously showed up as a hang.

10. **Docker path was untested.** `docker compose up --build` was run for real, the browser flow above passed against the containers, and the load test and `/metrics` were checked against the containerised server.

Verification of the round: 38 server tests, 7 client unit tests, the browser flow, ruff, mypy `--strict`, eslint/oxlint, vue-tsc and a production build all pass locally.
