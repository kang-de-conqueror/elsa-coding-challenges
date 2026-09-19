"""WebSocket wire protocol (version 1).

This module is the single source of truth for the message contract described in
``design/SYSTEM_DESIGN.md`` and ``design/adr/0001-websocket-vs-alternatives.md``.
Every message on the wire is a JSON object with a top-level ``v`` (protocol
version) and ``type`` field. Incoming messages are parsed with
``parse_client_message`` which dispatches on ``type`` before validating the
rest of the payload, so unknown/malformed input always produces a typed
``ErrorMessage`` instead of an unhandled exception.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

PROTOCOL_VERSION = 1


class ErrorCode:
    """Stable error codes returned to clients (never raw exception text)."""

    INVALID_MESSAGE = "INVALID_MESSAGE"
    QUIZ_NOT_FOUND = "QUIZ_NOT_FOUND"
    QUIZ_ALREADY_STARTED = "QUIZ_ALREADY_STARTED"
    DUPLICATE_USERNAME = "DUPLICATE_USERNAME"
    RATE_LIMITED = "RATE_LIMITED"
    UNKNOWN_USER = "UNKNOWN_USER"
    NO_ACTIVE_QUESTION = "NO_ACTIVE_QUESTION"


# ---------------------------------------------------------------------------
# Client -> Server
# ---------------------------------------------------------------------------


class JoinMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["join"] = "join"
    quiz_id: str = Field(min_length=1, max_length=64)
    username: str = Field(min_length=1, max_length=24)


class RejoinMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["rejoin"] = "rejoin"
    quiz_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)


class StartMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["start"] = "start"
    quiz_id: str = Field(min_length=1, max_length=64)


class AnswerMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["answer"] = "answer"
    request_id: str = Field(min_length=1, max_length=64)
    question_id: str = Field(min_length=1, max_length=64)
    choice_index: int = Field(ge=0, le=15)


class PingMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["ping"] = "ping"


ClientMessage = Annotated[
    JoinMessage | RejoinMessage | StartMessage | AnswerMessage | PingMessage,
    Field(discriminator="type"),
]

_client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def parse_client_message(raw: dict[str, object]) -> ClientMessage:
    """Validate a decoded JSON object against the client message union.

    Raises ``pydantic.ValidationError`` on malformed/unknown payloads; callers
    are expected to catch it and reply with ``ErrorMessage(code=INVALID_MESSAGE)``.
    """

    return _client_message_adapter.validate_python(raw)


__all_client_errors__ = (ValidationError,)


# ---------------------------------------------------------------------------
# Server -> Client
# ---------------------------------------------------------------------------


class ParticipantView(BaseModel):
    user_id: str
    username: str
    connected: bool


class JoinedMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["joined"] = "joined"
    quiz_id: str
    user_id: str
    username: str
    state: Literal["lobby", "in_progress", "finished"]


class ErrorMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["error"] = "error"
    code: str
    message: str


class ParticipantUpdateMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["participant_update"] = "participant_update"
    participants: list[ParticipantView]


class QuestionMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["question"] = "question"
    question_id: str
    index: int
    total: int
    text: str
    choices: list[str]
    duration_ms: int
    server_time_ms: int


class ScoreUpdateMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["score_update"] = "score_update"
    user_id: str
    question_id: str
    correct: bool
    points_awarded: int
    total_score: int


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    username: str
    score: int


class LeaderboardMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["leaderboard"] = "leaderboard"
    standings: list[LeaderboardEntry]


class QuizEndMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["quiz_end"] = "quiz_end"
    final_standings: list[LeaderboardEntry]


class PongMessage(BaseModel):
    v: int = PROTOCOL_VERSION
    type: Literal["pong"] = "pong"


ServerMessage = (
    JoinedMessage
    | ErrorMessage
    | ParticipantUpdateMessage
    | QuestionMessage
    | ScoreUpdateMessage
    | LeaderboardMessage
    | QuizEndMessage
    | PongMessage
)
