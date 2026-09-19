# ADR 0002: In-memory session store for this challenge, Redis-backed as the documented scale-out path

## Status

Accepted (with a deliberately deferred alternative)

## Context

Quiz session state (participants, current question, scores) needs to live somewhere. Two realistic options for this challenge:

1. **In-memory, single process** — state lives in a Python `dict` inside the one running server process, guarded by an `asyncio.Lock` per quiz room.
2. **Redis-backed, multi-process/multi-instance** — state lives in Redis (hashes for participant records, a sorted set (`ZSET`) for the leaderboard so ranking is O(log N) per update instead of an O(N log N) sort), and WebSocket servers publish score/leaderboard events over Redis Pub/Sub so any instance can serve any client and all instances stay in sync.

The challenge brief explicitly asks candidates to "implement one core real-time component... mock the rest" and to discuss scalability trade-offs, not to stand up a production-grade fleet. Standing up Redis, a pub/sub fan-out layer, and multi-instance deployment would be substantial additional scope for a coding challenge, and — done half-heartedly under time pressure — is more likely to introduce subtle distributed-systems bugs than to demonstrate engineering judgment.

## Decision

Ship the in-memory implementation (`InMemorySessionStore` in `server/app/session_store.py`), but put a narrow `SessionStore` interface (`get_or_create`, `get`) between the WebSocket handlers and the storage so a `RedisSessionStore` implementing the same interface is a composition-root swap (`main.py`), not a rewrite of `quiz.py` or the WebSocket handlers. Do not implement the Redis backend.

If/when this needed to run across multiple instances:

- **State**: participant records and scores move to Redis hashes/sorted sets, keyed by `quiz_id`. The `QuizSession` per-room `asyncio.Lock` is replaced by a Redis-based lock (e.g. `SET NX PX` or a library like `redis-py`'s `Lock`) or, better, by routing all mutations for a given `quiz_id` through a single owning instance (sharding rooms across instances) so no distributed lock is needed on the hot path at all.
- **Fan-out**: `ConnectionManager.broadcast` publishes to a Redis Pub/Sub channel named after `quiz_id`; every instance subscribes to the channels for the rooms it has local WebSocket connections for, and relays incoming messages to its local sockets. This turns the current single-process O(participants) broadcast into O(participants-on-this-instance) + one Redis publish.
- **Consistency**: correctness of scoring still depends on all mutations for one quiz room being serialized somewhere (either via the sharding-by-room strategy above, or a distributed lock). This is the same design constraint as today's per-session `asyncio.Lock`, just relocated.

## Consequences

- Today: zero operational dependencies (no Redis to run/monitor for local dev or the demo), and the state machine (`quiz.py`) is trivially unit-testable with plain `asyncio.Lock` semantics — see `tests/test_session.py`'s concurrency test, which would be materially harder to write deterministically against a real Redis instance.
- Today: **no durability** (a server restart loses all in-flight quizzes) and **no horizontal scaling** (one process is the hard ceiling on concurrent participants/rooms). Both are explicit, documented trade-offs, not oversights — see "Out of scope" in `SYSTEM_DESIGN.md`.
- Tomorrow: the `SessionStore` interface exists specifically so this decision is revisitable without a rewrite. This is the one abstraction introduced ahead of strict present-tense need in this codebase; it is justified by the challenge explicitly asking for a documented scalability story, not spec-anticipation for its own sake.
