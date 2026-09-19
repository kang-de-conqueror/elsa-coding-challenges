"""Per-room WebSocket registry, broadcast, and per-connection rate limiting.

Kept separate from ``QuizSession`` so the state machine stays transport-free
and unit-testable without a real socket (see ``tests/test_session.py``).
"""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import suppress

from fastapi import WebSocket
from pydantic import BaseModel

from app.observability import ACTIVE_CONNECTIONS, get_logger, log_event, track_broadcast_latency

logger = get_logger("app.connection_manager")


class RateLimiter:
    """Simple per-key token bucket, e.g. to cap answer-message spam."""

    def __init__(self, *, max_tokens: int, refill_seconds: float) -> None:
        self._max_tokens = max_tokens
        self._refill_seconds = refill_seconds
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last_refill = self._buckets.get(key, (float(self._max_tokens), now))
        elapsed = now - last_refill
        refill_rate = self._max_tokens / self._refill_seconds
        tokens = min(self._max_tokens, tokens + elapsed * refill_rate)
        if tokens < 1:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1, now)
        return True

    def drop(self, key: str) -> None:
        self._buckets.pop(key, None)


class ConnectionManager:
    """Owns the room registry, broadcast fan-out, rate limiting, and idle
    connection reaping.

    A clean client disconnect is caught by the WebSocket receive loop
    raising ``WebSocketDisconnect`` (see ``main.py``). A half-open
    connection (network drop without a close frame, e.g. a laptop going to
    sleep) is not: nothing ever raises. ``touch``/``reap_idle`` cover that
    case by tracking last-seen-alive per connection and force-closing ones
    that go quiet for longer than ``idle_timeout_seconds``.
    """

    def __init__(self, *, idle_timeout_seconds: float = 60.0) -> None:
        self._rooms: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self._last_seen: dict[tuple[str, str], float] = {}
        self.idle_timeout_seconds = idle_timeout_seconds
        self.answer_rate_limiter = RateLimiter(max_tokens=5, refill_seconds=5.0)

    def register(self, quiz_id: str, user_id: str, websocket: WebSocket) -> None:
        self._rooms[quiz_id][user_id] = websocket
        self._last_seen[(quiz_id, user_id)] = time.monotonic()
        ACTIVE_CONNECTIONS.inc()

    def unregister(self, quiz_id: str, user_id: str) -> None:
        room = self._rooms.get(quiz_id)
        if room and room.pop(user_id, None) is not None:
            ACTIVE_CONNECTIONS.dec()
        self._last_seen.pop((quiz_id, user_id), None)
        self.answer_rate_limiter.drop(user_id)
        if room is not None and not room:
            self._rooms.pop(quiz_id, None)

    def touch(self, quiz_id: str, user_id: str) -> None:
        """Record that a connection is alive (any inbound message, not just ping)."""

        if (quiz_id, user_id) in self._last_seen:
            self._last_seen[(quiz_id, user_id)] = time.monotonic()

    async def reap_idle_connections(self) -> None:
        """Force-close connections that have been silent past the idle timeout."""

        now = time.monotonic()
        stale = [
            key for key, last_seen in self._last_seen.items() if now - last_seen > self.idle_timeout_seconds
        ]
        for quiz_id, user_id in stale:
            websocket = self._rooms.get(quiz_id, {}).get(user_id)
            self.unregister(quiz_id, user_id)
            if websocket is not None:
                log_event(logger, "idle_connection_reaped", quiz_id=quiz_id, user_id=user_id)
                with suppress(Exception):
                    await websocket.close(code=1000)

    def connection_count(self, quiz_id: str) -> int:
        return len(self._rooms.get(quiz_id, {}))

    async def send_to(self, quiz_id: str, user_id: str, message: BaseModel) -> None:
        websocket = self._rooms.get(quiz_id, {}).get(user_id)
        if websocket is None:
            return
        await self._safe_send(quiz_id, user_id, websocket, message)

    async def broadcast(self, quiz_id: str, message: BaseModel) -> None:
        room = dict(self._rooms.get(quiz_id, {}))
        if not room:
            return
        with track_broadcast_latency():
            for user_id, websocket in room.items():
                await self._safe_send(quiz_id, user_id, websocket, message)

    async def _safe_send(self, quiz_id: str, user_id: str, websocket: WebSocket, message: BaseModel) -> None:
        try:
            await websocket.send_text(message.model_dump_json())
        except Exception:
            # A dead/half-closed socket must not take the whole broadcast down;
            # the receive loop for that connection will observe the disconnect
            # and clean up participant state.
            log_event(logger, "send_failed", quiz_id=quiz_id, user_id=user_id)
            self.unregister(quiz_id, user_id)
