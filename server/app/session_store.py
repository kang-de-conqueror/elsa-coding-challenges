"""Quiz session storage.

``SessionStore`` is deliberately the narrowest interface that both call
sites (``main.py`` and the test suite) need. The only implementation today
is ``InMemorySessionStore``. The interface exists so that a future
Redis-backed store (see ADR 0002) is a drop-in swap at the composition root
in ``main.py`` rather than a rewrite of the WebSocket handling code -- it is
not implemented here because this challenge scopes a single-process
deployment.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Protocol

from app.quiz import Question, QuizSession


class SessionStore(Protocol):
    async def get_or_create(
        self, quiz_id: str, questions_factory: Callable[[], list[Question]]
    ) -> QuizSession: ...

    async def get(self, quiz_id: str) -> QuizSession | None: ...

    async def remove(self, quiz_id: str) -> None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, QuizSession] = {}
        # Guards creation of new sessions only; per-session mutations use the
        # session's own lock (app/quiz.py) so unrelated rooms never contend.
        self._creation_lock = asyncio.Lock()

    async def get_or_create(
        self, quiz_id: str, questions_factory: Callable[[], list[Question]]
    ) -> QuizSession:
        existing = self._sessions.get(quiz_id)
        if existing is not None:
            return existing
        async with self._creation_lock:
            existing = self._sessions.get(quiz_id)
            if existing is not None:
                return existing
            session = QuizSession(quiz_id=quiz_id, questions=questions_factory())
            self._sessions[quiz_id] = session
            return session

    async def get(self, quiz_id: str) -> QuizSession | None:
        return self._sessions.get(quiz_id)

    async def remove(self, quiz_id: str) -> None:
        self._sessions.pop(quiz_id, None)

    def active_session_count(self) -> int:
        return len(self._sessions)
