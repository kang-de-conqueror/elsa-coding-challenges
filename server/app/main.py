"""FastAPI application: WebSocket quiz endpoint, health check, and metrics.

This module is the composition root: it wires ``SessionStore``,
``ConnectionManager`` and the ``QuizSession`` state machine to the WebSocket
transport, and owns the one background task per quiz room that advances
questions on a timer.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import ValidationError

from app.connection_manager import ConnectionManager
from app.observability import (
    ACTIVE_SESSIONS,
    ANSWERS_PROCESSED,
    MESSAGES_REJECTED,
    REGISTRY,
    get_logger,
    log_event,
    setup_logging,
)
from app.quiz import QuizError, QuizSession, mock_question_bank
from app.schemas import (
    AnswerMessage,
    ErrorCode,
    ErrorMessage,
    JoinedMessage,
    JoinMessage,
    LeaderboardEntry,
    LeaderboardMessage,
    ParticipantUpdateMessage,
    ParticipantView,
    PingMessage,
    PongMessage,
    QuestionMessage,
    QuizEndMessage,
    RejoinMessage,
    ScoreUpdateMessage,
    StartMessage,
    parse_client_message,
)
from app.session_store import InMemorySessionStore

setup_logging()
logger = get_logger("app.main")

REAP_INTERVAL_SECONDS = 15.0

store = InMemorySessionStore()
connections = ConnectionManager()
_quiz_runner_tasks: dict[str, asyncio.Task[None]] = {}


async def _reap_idle_connections_periodically() -> None:
    while True:
        await asyncio.sleep(REAP_INTERVAL_SECONDS)
        await connections.reap_idle_connections()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    reaper = asyncio.create_task(_reap_idle_connections_periodically())
    try:
        yield
    finally:
        reaper.cancel()


app = FastAPI(title="ELSA Real-Time Quiz", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    ACTIVE_SESSIONS.set(store.active_session_count())
    return PlainTextResponse(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


def _participant_update(session: QuizSession) -> ParticipantUpdateMessage:
    return ParticipantUpdateMessage(
        participants=[
            ParticipantView(user_id=p.user_id, username=p.username, connected=p.connected)
            for p in session.participants.values()
        ]
    )


def _leaderboard_entries(session: QuizSession) -> list[LeaderboardEntry]:
    return [
        LeaderboardEntry(rank=e.rank, user_id=e.user_id, username=e.username, score=e.score)
        for e in session.leaderboard()
    ]


def _leaderboard_message(session: QuizSession) -> LeaderboardMessage:
    return LeaderboardMessage(standings=_leaderboard_entries(session))


# Broadcasting the full leaderboard to every participant after *every single*
# answer is O(participants^2) in the worst case: a burst of N answers each
# fan out to N sockets. A 300-client load test (scripts/load_test.py)
# measured this directly -- mean answer-ack latency ~5s, because the event
# loop was stuck working through a backlog of O(N^2) sequential sends. This
# debounces same-quiz leaderboard broadcasts: a burst of answers within
# LEADERBOARD_DEBOUNCE_SECONDS collapses into a single broadcast of the
# latest state, turning worst-case cost into O(participants) per window.
LEADERBOARD_DEBOUNCE_SECONDS = 0.15
_pending_leaderboard_broadcasts: dict[str, asyncio.Task[None]] = {}


async def _fire_leaderboard_broadcast(session: QuizSession) -> None:
    await asyncio.sleep(LEADERBOARD_DEBOUNCE_SECONDS)
    _pending_leaderboard_broadcasts.pop(session.quiz_id, None)
    await connections.broadcast(session.quiz_id, _leaderboard_message(session))


def _schedule_leaderboard_broadcast(session: QuizSession) -> None:
    if session.quiz_id in _pending_leaderboard_broadcasts:
        return  # already scheduled; it reads current state when it fires
    _pending_leaderboard_broadcasts[session.quiz_id] = asyncio.create_task(
        _fire_leaderboard_broadcast(session)
    )


async def _run_quiz(session: QuizSession) -> None:
    """Owns the question timer for one quiz room: broadcast -> sleep -> advance."""

    question = session.current_question
    try:
        while question is not None:
            await connections.broadcast(
                session.quiz_id,
                QuestionMessage(
                    question_id=question.id,
                    index=session.current_question_index,
                    total=len(session.questions),
                    text=question.text,
                    choices=question.choices,
                    duration_ms=question.duration_ms,
                    server_time_ms=int(time.time() * 1000),
                ),
            )
            await asyncio.sleep(question.duration_ms / 1000)
            await connections.broadcast(session.quiz_id, _leaderboard_message(session))
            question = await session.advance_question()

        await connections.broadcast(
            session.quiz_id,
            QuizEndMessage(final_standings=_leaderboard_entries(session)),
        )
        log_event(logger, "quiz_finished", quiz_id=session.quiz_id)
    finally:
        _quiz_runner_tasks.pop(session.quiz_id, None)


async def _reject(websocket: WebSocket, code: str, message: str) -> None:
    await websocket.send_text(ErrorMessage(code=code, message=message).model_dump_json())


async def _handle_join(websocket: WebSocket, message: JoinMessage) -> str:
    session = await store.get_or_create(message.quiz_id, mock_question_bank)
    participant = await session.join(message.username)
    connections.register(message.quiz_id, participant.user_id, websocket)
    await websocket.send_text(
        JoinedMessage(
            quiz_id=message.quiz_id,
            user_id=participant.user_id,
            username=participant.username,
            state=session.state.value,
        ).model_dump_json()
    )
    await connections.broadcast(message.quiz_id, _participant_update(session))
    log_event(logger, "participant_joined", quiz_id=message.quiz_id, user_id=participant.user_id)
    return participant.user_id


async def _handle_rejoin(websocket: WebSocket, message: RejoinMessage) -> str:
    session = await store.get(message.quiz_id)
    if session is None:
        raise QuizError(ErrorCode.QUIZ_NOT_FOUND, "No quiz with that id.")
    participant = await session.rejoin(message.user_id)
    connections.register(message.quiz_id, participant.user_id, websocket)
    await websocket.send_text(
        JoinedMessage(
            quiz_id=message.quiz_id,
            user_id=participant.user_id,
            username=participant.username,
            state=session.state.value,
        ).model_dump_json()
    )
    current = session.current_question
    await websocket.send_text(
        ScoreUpdateMessage(
            user_id=participant.user_id,
            question_id=current.id if current else "",
            correct=False,
            points_awarded=0,
            total_score=participant.score,
        ).model_dump_json()
    )
    await connections.broadcast(message.quiz_id, _participant_update(session))
    log_event(logger, "participant_rejoined", quiz_id=message.quiz_id, user_id=participant.user_id)
    return participant.user_id


async def _handle_start(message: StartMessage) -> None:
    session = await store.get(message.quiz_id)
    if session is None:
        raise QuizError(ErrorCode.QUIZ_NOT_FOUND, "No quiz with that id.")
    await session.start()
    _quiz_runner_tasks[message.quiz_id] = asyncio.create_task(_run_quiz(session))
    log_event(logger, "quiz_started", quiz_id=message.quiz_id)


async def _handle_answer(websocket: WebSocket, quiz_id: str, user_id: str, message: AnswerMessage) -> None:
    if not connections.answer_rate_limiter.allow(user_id):
        MESSAGES_REJECTED.labels(reason="rate_limited").inc()
        raise QuizError(ErrorCode.RATE_LIMITED, "Too many answers submitted too quickly.")
    session = await store.get(quiz_id)
    if session is None:
        raise QuizError(ErrorCode.QUIZ_NOT_FOUND, "No quiz with that id.")
    result = await session.submit_answer(
        user_id=user_id,
        question_id=message.question_id,
        choice_index=message.choice_index,
        request_id=message.request_id,
    )
    ANSWERS_PROCESSED.labels(correct=str(result.correct).lower()).inc()
    await websocket.send_text(
        ScoreUpdateMessage(
            user_id=user_id,
            question_id=message.question_id,
            correct=result.correct,
            points_awarded=result.points_awarded,
            total_score=result.total_score,
        ).model_dump_json()
    )
    if not result.duplicate:
        _schedule_leaderboard_broadcast(session)


@app.websocket("/ws/{quiz_id}")
async def websocket_endpoint(websocket: WebSocket, quiz_id: str) -> None:
    await websocket.accept()
    user_id: str | None = None

    try:
        while True:
            try:
                raw = await websocket.receive_json()
                if user_id is not None:
                    connections.touch(quiz_id, user_id)
            except ValueError:
                MESSAGES_REJECTED.labels(reason="malformed_json").inc()
                await _reject(websocket, ErrorCode.INVALID_MESSAGE, "Message must be valid JSON.")
                continue

            try:
                message = parse_client_message(raw)
            except ValidationError:
                MESSAGES_REJECTED.labels(reason="invalid_schema").inc()
                await _reject(websocket, ErrorCode.INVALID_MESSAGE, "Message failed schema validation.")
                continue

            try:
                if isinstance(message, JoinMessage):
                    user_id = await _handle_join(websocket, message)
                elif isinstance(message, RejoinMessage):
                    user_id = await _handle_rejoin(websocket, message)
                elif isinstance(message, StartMessage):
                    await _handle_start(message)
                elif isinstance(message, AnswerMessage):
                    if user_id is None:
                        raise QuizError(ErrorCode.UNKNOWN_USER, "Join a quiz before answering.")
                    await _handle_answer(websocket, quiz_id, user_id, message)
                elif isinstance(message, PingMessage):
                    await websocket.send_text(PongMessage().model_dump_json())
            except QuizError as exc:
                await _reject(websocket, exc.code, exc.message)

    except WebSocketDisconnect:
        pass
    finally:
        if user_id is not None:
            connections.unregister(quiz_id, user_id)
            session = await store.get(quiz_id)
            if session is not None:
                session.mark_disconnected(user_id)
                await connections.broadcast(quiz_id, _participant_update(session))
            log_event(logger, "participant_disconnected", quiz_id=quiz_id, user_id=user_id)
