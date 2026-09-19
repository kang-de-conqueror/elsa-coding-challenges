"""Pure scoring and ranking functions.

Kept free of I/O and asyncio so they can be unit tested as plain functions
(see ``tests/test_scoring.py``). Scoring never trusts a client-supplied
timestamp: callers must pass ``remaining_ms`` already computed from the
server's own clock (see ``quiz.QuizSession.submit_answer``).
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_POINTS = 1000
MAX_SPEED_BONUS = 500


def calculate_points(*, correct: bool, remaining_ms: int, duration_ms: int) -> int:
    """Score a single answer.

    A correct answer always earns ``BASE_POINTS``, plus a speed bonus of up
    to ``MAX_SPEED_BONUS`` proportional to how much time was left on the
    clock when the server received the answer. An incorrect (or late, i.e.
    ``remaining_ms <= 0``) answer earns 0.
    """

    if not correct or duration_ms <= 0:
        return 0
    clamped_remaining = max(0, min(remaining_ms, duration_ms))
    bonus = round(MAX_SPEED_BONUS * clamped_remaining / duration_ms)
    return BASE_POINTS + bonus


@dataclass(frozen=True)
class RankableParticipant:
    user_id: str
    username: str
    score: int
    total_response_ms: int
    join_order: int


@dataclass(frozen=True)
class RankedEntry:
    rank: int
    user_id: str
    username: str
    score: int


def build_leaderboard(participants: list[RankableParticipant]) -> list[RankedEntry]:
    """Rank participants for the leaderboard.

    Tie-break order (deterministic, so results are reproducible in tests):
    1. Higher score wins.
    2. Lower cumulative response time wins (rewards consistently fast answers).
    3. Earlier join order wins (stable fallback so ranks never depend on
       dict/set iteration order).
    """

    ordered = sorted(
        participants,
        key=lambda p: (-p.score, p.total_response_ms, p.join_order),
    )
    return [
        RankedEntry(rank=i + 1, user_id=p.user_id, username=p.username, score=p.score)
        for i, p in enumerate(ordered)
    ]
