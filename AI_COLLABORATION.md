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

**Verification**: the protocol was cross-checked for completeness against every UI state the client would need (lobby, in-progress, finished, disconnected/rejoining) before any server code was written, catching one gap early (rejoin needed to replay the participant's current score, not just confirm the connection — see `_handle_rejoin` sending a `score_update` alongside `joined`). The scoring/tie-break design was validated after the fact with unit tests (`server/tests/test_scoring.py`) covering boundary cases (zero time remaining, full time remaining, negative/over-range clamping, all three tie-break levels) — see "Server implementation" below.

## Server implementation

**Task**: the FastAPI/WebSocket backend — `quiz.py` (state machine), `scoring.py`, `connection_manager.py`, `session_store.py`, `observability.py`, `main.py`, and the full test suite.

**AI's role**: Claude Code wrote all of the above from the agreed design, including the concurrency-safety approach (`asyncio.Lock` per quiz room) and the idempotent-answer design (dedup by client-generated `request_id`).

**Verification** (concrete, not just "it looked right"):

- `ruff check` and `mypy --strict` were run after every file, and every finding was fixed before moving on — not deferred to a final pass. Two real strict-mode gaps were caught and fixed this way: an untyped `dict` parameter (`schemas.py::parse_client_message`) and several lines exceeding the configured line-length that would have failed CI.
- The full pytest suite (22 tests) was run repeatedly during development, including a targeted concurrency test (`test_concurrent_answers_from_many_participants_never_corrupt_state`) that fires 50 simultaneous `submit_answer` calls via `asyncio.gather` specifically to catch a lost-update bug if the per-session lock were ever removed or misapplied — this is a regression test for a class of bug, not just a happy-path check.
- The integration test (`test_integration_ws.py`) runs the *real* FastAPI app (not a mock) with three concurrent simulated WebSocket clients through a full join -> start -> answer -> quiz_end flow, asserting the final leaderboard ranking is correct.
- The server was actually started (`uvicorn app.main:app`) and hit with real HTTP/WebSocket traffic (`curl /healthz`, `curl /metrics`) to confirm it boots and serves correctly outside the test harness — catching issues a unit test alone wouldn't (e.g. the FastAPI `lifespan` wiring for the idle-connection reaper background task).
- **A load test caught a real bug that code review alone had missed.** `scripts/load_test.py` was written and run against the live server at increasing scale (50 -> 100 -> 150 -> 200 -> 300 simulated clients). The first 300-client run measured a mean answer-ack latency of ~5 seconds — nowhere near the <150ms target. Rather than accepting or hand-waving this, the broadcast code path was re-read, which revealed an O(N²) bug: the full leaderboard was being broadcast to all N participants after *every single* answer, so a synchronized burst of N answers costs N x N sequential sends. This was fixed with a 150ms debounce/coalescing window (`main.py::_schedule_leaderboard_broadcast`), and the *same* load test was re-run to confirm the fix: leaderboard fan-out spread dropped from 1481ms to 265ms and median ack latency dropped from ~6.0s to ~0.9s at 300 clients (full numbers and methodology in `design/SYSTEM_DESIGN.md`, section 7). The originally planned NFR ("300-500 concurrent participants") was revised downward to a measured, honest number after this data, rather than left as an unverified assumption.

## Client implementation

**Task**: the Vue 3/TypeScript/Pinia frontend — protocol types, the `useQuizSocket` composable (connection lifecycle, reconnect with backoff, heartbeat, rejoin-from-localStorage), the Pinia store, and all five components/views.

**AI's role**: Claude Code scaffolded the project (`npm create vue@latest`) and wrote all application code against the same protocol contract as the server.

**Verification**:

- `vue-tsc --build` (strict TypeScript project references) and `eslint`/`oxlint` were run and fixed to a clean state (one real issue caught: a single-word component name, `Leaderboard.vue`, violating the Vue style guide's multi-word component rule — renamed to `LeaderboardPanel.vue`).
- A production build (`vite build`) was run to confirm the app actually compiles and bundles, not just type-checks in isolation.
- **Explicit limitation, stated rather than glossed over**: this sandboxed environment has no browser-automation tool available, so the UI was *not* visually exercised in a real browser as part of this session. To still verify the client's WebSocket usage was correct rather than assuming it, a small Node script was written that sends and receives the exact same message shapes `useQuizSocket.ts` does (join -> start -> question -> answer -> score_update -> leaderboard -> next question), run against the live server. It confirmed the full message cycle works end-to-end across two simulated clients through multiple question rounds. This is real verification of the protocol contract the UI depends on, but it is **not** a substitute for a real browser check (DOM rendering, CSS, click handling, countdown timer accuracy) — that check is still outstanding and should be the first thing a human reviewer does before treating this as fully verified.

## Infrastructure and docs

**Task**: `pyproject.toml` (ruff/mypy/pytest config), `Dockerfile`s, `docker-compose.yml`, `.github/workflows/ci.yml`, the design document, ADRs, and this file.

**AI's role**: written directly by Claude Code, using the same lint/type-check/test commands locally as configured in CI, so CI is expected to reproduce local results rather than being an untested guess.

**Verification**: the Docker Compose health check depends on the same `/healthz` endpoint exercised manually above; the CI workflow runs the exact commands already verified locally in this session (`ruff check`, `mypy app`, `pytest -q`, `npm run lint`, `npm run type-check`, `npm run build`) rather than a different, untested command set — but the CI workflow itself has not been run against GitHub Actions as part of this session (no push was made), so it should be treated as "written and locally-equivalent-verified," not "confirmed green in CI."

## Honest summary of what is and isn't verified

**Verified in this session**: server correctness under concurrency (automated + load test), server API surface (manual + automated), the WebSocket protocol contract end-to-end (both server-side integration test and a client-shaped script), static analysis (lint + strict types) on both server and client, and that the client builds.

**Not verified in this session**: the Vue UI's actual rendered appearance and interaction behavior in a real browser, and the GitHub Actions CI workflow's behavior on GitHub's own runners. Both should be checked before this is presented as a finished submission.
