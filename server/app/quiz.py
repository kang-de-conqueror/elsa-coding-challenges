"""Quiz session state machine.

A ``QuizSession`` owns everything about one quiz room: participants, the
current question, and scores. All mutations go through methods that acquire
the session's own ``asyncio.Lock`` so concurrent answer submissions (the
common case: many participants answering within the same event-loop tick)
can never interleave into a lost update. The lock is per-session, not
global, so unrelated quiz rooms never contend with each other.

State machine: ``LOBBY -> IN_PROGRESS -> FINISHED``. There is no path back;
a finished quiz is retained for a grace period (so late clients can rejoin and
see the final standings) and then removed by ``main.py``; nothing survives a
process restart (see ADR 0002 for why durability is explicitly out of scope).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from app.scoring import RankableParticipant, RankedEntry, build_leaderboard, calculate_points


class QuizState(StrEnum):
    LOBBY = "lobby"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class QuizError(Exception):
    """Raised with a stable ``code`` matching ``schemas.ErrorCode``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    choices: list[str]
    correct_index: int
    duration_ms: int


@dataclass
class Participant:
    user_id: str
    username: str
    join_order: int
    connected: bool = True
    score: int = 0
    total_response_ms: int = 0
    answered_question_ids: set[str] = field(default_factory=set)
    seen_request_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class AnswerResult:
    correct: bool
    points_awarded: int
    total_score: int
    duplicate: bool = False


def mock_question_bank() -> list[Question]:
    """Static in-memory question set standing in for a real question service.

    Mocking the question bank (rather than the real-time transport) is the
    intentional scope cut for this challenge: see "Out of scope" in
    ``design/SYSTEM_DESIGN.md``.
    """

    raw = [
        ("What is a synonym for 'happy'?", ["Sad", "Joyful", "Angry", "Tired"], 1),
        ("Choose the correct past tense of 'go'.", ["Goed", "Gone", "Went", "Going"], 2),
        ("'Elsa' helps users practice which skill?", ["Cooking", "Pronunciation", "Driving", "Painting"], 1),
        ("Which word means the opposite of 'fast'?", ["Quick", "Slow", "Rapid", "Swift"], 1),
        ("Complete: 'She ___ to the store yesterday.'", ["go", "goes", "went", "going"], 2),
    ]
    return [
        Question(id=f"q{i + 1}", text=text, choices=choices, correct_index=correct, duration_ms=15_000)
        for i, (text, choices, correct) in enumerate(raw)
    ]


class QuizSession:
    def __init__(self, quiz_id: str, questions: list[Question]) -> None:
        self.quiz_id = quiz_id
        self.questions = questions
        self.state = QuizState.LOBBY
        self.participants: dict[str, Participant] = {}
        self.current_question_index: int = -1
        self._current_question_started_at: float | None = None  # time.monotonic()
        self._join_counter = 0
        self.lock = asyncio.Lock()

    # -- read-only helpers (safe without the lock: dict/attr reads are atomic
    #    under asyncio's single-threaded event loop; only multi-step
    #    mutations need the lock) --

    @property
    def current_question(self) -> Question | None:
        if 0 <= self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None

    def remaining_ms(self) -> int:
        """Time left on the active question, measured on the server's monotonic clock."""

        question = self.current_question
        if question is None or self._current_question_started_at is None:
            return 0
        elapsed_ms = int((time.monotonic() - self._current_question_started_at) * 1000)
        return max(0, question.duration_ms - elapsed_ms)

    def leaderboard(self) -> list[RankedEntry]:
        rankable = [
            RankableParticipant(
                user_id=p.user_id,
                username=p.username,
                score=p.score,
                total_response_ms=p.total_response_ms,
                join_order=p.join_order,
            )
            for p in self.participants.values()
        ]
        return build_leaderboard(rankable)

    # -- mutations --

    async def join(self, username: str) -> Participant:
        async with self.lock:
            if self.state != QuizState.LOBBY:
                raise QuizError("QUIZ_ALREADY_STARTED", "Quiz has already started; join before it starts.")
            if any(p.username == username for p in self.participants.values()):
                raise QuizError("DUPLICATE_USERNAME", f"Username '{username}' is already taken in this quiz.")
            user_id = uuid.uuid4().hex
            participant = Participant(user_id=user_id, username=username, join_order=self._join_counter)
            self._join_counter += 1
            self.participants[user_id] = participant
            return participant

    async def rejoin(self, user_id: str) -> Participant:
        async with self.lock:
            participant = self.participants.get(user_id)
            if participant is None:
                raise QuizError("UNKNOWN_USER", "No participant with that id in this quiz.")
            participant.connected = True
            return participant

    def mark_disconnected(self, user_id: str) -> None:
        participant = self.participants.get(user_id)
        if participant is not None:
            participant.connected = False

    async def start(self) -> Question:
        async with self.lock:
            if self.state != QuizState.LOBBY:
                raise QuizError("QUIZ_ALREADY_STARTED", "Quiz has already started.")
            self.state = QuizState.IN_PROGRESS
            self.current_question_index = 0
            self._current_question_started_at = time.monotonic()
            return self.questions[0]

    async def advance_question(self) -> Question | None:
        """Move to the next question, or finish the quiz if none remain."""

        async with self.lock:
            if self.state != QuizState.IN_PROGRESS:
                return None
            self.current_question_index += 1
            if self.current_question_index >= len(self.questions):
                self.state = QuizState.FINISHED
                self._current_question_started_at = None
                return None
            self._current_question_started_at = time.monotonic()
            return self.questions[self.current_question_index]

    async def submit_answer(
        self, *, user_id: str, question_id: str, choice_index: int, request_id: str
    ) -> AnswerResult:
        async with self.lock:
            if self.state != QuizState.IN_PROGRESS:
                raise QuizError("NO_ACTIVE_QUESTION", "No question is currently active.")
            question = self.current_question
            if question is None or question.id != question_id:
                raise QuizError("NO_ACTIVE_QUESTION", "That question is no longer active.")
            participant = self.participants.get(user_id)
            if participant is None:
                raise QuizError("UNKNOWN_USER", "No participant with that id in this quiz.")

            if request_id in participant.seen_request_ids:
                # Idempotent replay (client retry after a dropped ack): return the
                # already-applied result instead of scoring twice.
                return AnswerResult(
                    correct=question_id in participant.answered_question_ids,
                    points_awarded=0,
                    total_score=participant.score,
                    duplicate=True,
                )
            participant.seen_request_ids.add(request_id)

            if question_id in participant.answered_question_ids:
                return AnswerResult(
                    correct=False, points_awarded=0, total_score=participant.score, duplicate=True
                )

            assert self._current_question_started_at is not None
            elapsed_ms = int((time.monotonic() - self._current_question_started_at) * 1000)
            remaining_ms = question.duration_ms - elapsed_ms
            correct = choice_index == question.correct_index and remaining_ms > 0
            points = calculate_points(
                correct=correct, remaining_ms=remaining_ms, duration_ms=question.duration_ms
            )

            participant.answered_question_ids.add(question_id)
            participant.score += points
            participant.total_response_ms += max(0, min(elapsed_ms, question.duration_ms))

            return AnswerResult(correct=correct, points_awarded=points, total_score=participant.score)
