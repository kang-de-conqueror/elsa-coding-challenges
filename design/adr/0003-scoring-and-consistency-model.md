# ADR 0003: Scoring formula, tie-break rule, and consistency model

## Status

Accepted

## Context

Three related correctness questions need a single, testable answer:

1. How many points does an answer earn?
2. When two participants are tied on score, who ranks higher?
3. What consistency guarantee does the leaderboard offer under concurrent answers, and whose clock decides "on time" vs "late"?

## Decision

**Scoring** (`server/app/scoring.py::calculate_points`): a correct answer earns a fixed base (1000 points) plus a speed bonus of up to 500 points, linear in the fraction of the question's time window still remaining when the server received the answer (`remaining_ms / duration_ms`). An incorrect answer, or one that arrives after the question's time window has elapsed, earns 0. This is a well-understood, easy-to-explain-on-camera model (the same shape popular quiz apps use), and it rewards both correctness and speed without punishing a merely-slightly-slower-but-correct answer as harshly as a purely rank-based bonus would.

**Timestamp authority**: the elapsed time used for scoring is always `server_monotonic_now - question_started_at_server_monotonic` (see `QuizSession.submit_answer`), computed from `time.monotonic()` on the server. The client-sent `AnswerMessage` carries no timestamp field at all — there is nothing for a malicious or clock-skewed client to lie about. `time.monotonic()` (not `time.time()`) is used specifically because it cannot jump backwards or forwards due to NTP adjustments or system clock changes, which matters for a duration measurement held across an `await` boundary in an async server.

**Tie-break** (`build_leaderboard`): (1) higher score wins; (2) lower cumulative response time (sum of elapsed-ms across all answered questions) wins, rewarding consistently fast answers over one lucky fast answer; (3) earlier join order wins, as a final deterministic fallback so rank never depends on Python dict/set iteration order. All three criteria are pure, hand-testable functions with no I/O — see `tests/test_scoring.py`.

**Consistency model**: strong consistency *within one quiz room, within one process* — every mutation to a `QuizSession` (join, start, submit_answer, advance_question) is serialized behind that session's own `asyncio.Lock`, so two answers "arriving at the same time" (the common case under load: many participants answering within the same event-loop tick) can never interleave into a lost update. This is verified directly, not just argued, by `tests/test_session.py::test_concurrent_answers_from_many_participants_never_corrupt_state`, which fires 50 concurrent `submit_answer` calls via `asyncio.gather` and asserts every participant's score lands exactly once.

Cross-instance consistency is explicitly out of scope for the reasons in ADR 0002: there is only one process, so there is nothing to be inconsistent with.

## Consequences

- Scoring and ranking are pure functions, independent of the WebSocket transport and the lock — this is what makes them fast and reliable to unit test (`tests/test_scoring.py` has no `asyncio` dependency at all).
- Because the server never trusts a client timestamp, there is no way for a client to fabricate a faster answer than it actually sent — the anti-cheat property falls out of the design rather than needing a separate validation layer.
- The single per-session lock is also the reason the O(N²) leaderboard-broadcast issue found under load testing (see `SYSTEM_DESIGN.md`, "Capacity") was a broadcast-fan-out cost problem, not a correctness problem: the lock ensures scores were always correct even while 300 clients answered in the same instant, and profiling could focus purely on the broadcast path.
