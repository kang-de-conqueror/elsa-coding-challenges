"""WebSocket behaviours found during code review: rejoin resync, room binding,
join-before-start, single join per socket, and stale-socket cleanup."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.quiz import Question


def _bank() -> list[Question]:
    return [
        Question(id="q0", text="Q0?", choices=["a", "b", "c"], correct_index=1, duration_ms=5000),
        Question(id="q1", text="Q1?", choices=["a", "b", "c"], correct_index=1, duration_ms=5000),
    ]


@pytest.fixture(autouse=True)
def _slow_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "mock_question_bank", _bank)


def _until(ws: Any, message_type: str, limit: int = 30) -> dict[str, Any]:
    for _ in range(limit):
        message = ws.receive_json()
        if message["type"] == message_type:
            return message
    raise AssertionError(f"no '{message_type}' within {limit} messages")


def _join(ws: Any, room: str, name: str) -> str:
    ws.send_json({"type": "join", "quiz_id": room, "username": name})
    return str(_until(ws, "joined")["user_id"])


def test_rejoin_mid_quiz_resyncs_question_score_and_leaderboard() -> None:
    room = "resync-room"
    with TestClient(main_module.app) as client:
        with client.websocket_connect(f"/ws/{room}") as alice:
            alice_id = _join(alice, room, "alice")
            alice.send_json({"type": "start", "quiz_id": room})
            _until(alice, "question")
            alice.send_json(
                {"type": "answer", "request_id": "r1", "question_id": "q0", "choice_index": 1}
            )
            earned = _until(alice, "score_update")["total_score"]
            assert earned > 0

        with client.websocket_connect(f"/ws/{room}") as again:
            again.send_json({"type": "rejoin", "quiz_id": room, "user_id": alice_id})
            assert _until(again, "joined")["state"] == "in_progress"
            question = _until(again, "question")
            assert question["question_id"] == "q0"
            assert 0 < question["duration_ms"] <= 5000
            replay = _until(again, "score_update")  # the answer given before disconnecting
            assert replay["question_id"] == "q0"
            assert replay["correct"] is True
            assert replay["total_score"] == earned
            standings = _until(again, "leaderboard")["standings"]
            assert standings[0]["user_id"] == alice_id


def test_rejoin_before_answering_does_not_mark_the_question_answered() -> None:
    room = "unanswered-room"
    with TestClient(main_module.app) as client:
        with client.websocket_connect(f"/ws/{room}") as alice:
            alice_id = _join(alice, room, "alice")
            alice.send_json({"type": "start", "quiz_id": room})
            _until(alice, "question")

        with client.websocket_connect(f"/ws/{room}") as again:
            again.send_json({"type": "rejoin", "quiz_id": room, "user_id": alice_id})
            _until(again, "question")
            assert _until(again, "leaderboard")["standings"][0]["score"] == 0
            again.send_json({"type": "answer", "request_id": "r1", "question_id": "q0", "choice_index": 1})
            ack = _until(again, "score_update")
            assert ack["correct"] is True
            assert ack["points_awarded"] > 0


def test_stale_socket_closing_after_rejoin_does_not_evict_new_socket() -> None:
    room = "stale-room"
    with TestClient(main_module.app) as client:
        old = client.websocket_connect(f"/ws/{room}")
        old_ws = old.__enter__()
        user_id = _join(old_ws, room, "alice")

        with client.websocket_connect(f"/ws/{room}") as new_ws:
            new_ws.send_json({"type": "rejoin", "quiz_id": room, "user_id": user_id})
            _until(new_ws, "joined")
            old.__exit__(None, None, None)  # stale socket goes away after the rejoin

            new_ws.send_json({"type": "ping"})
            _until(new_ws, "pong")
            new_ws.send_json({"type": "start", "quiz_id": room})
            assert _until(new_ws, "question")["question_id"] == "q0"  # still registered

            participants = main_module.store._sessions[room].participants  # noqa: SLF001
            assert participants[user_id].connected is True


def test_message_for_a_different_room_is_rejected() -> None:
    with TestClient(main_module.app) as client, client.websocket_connect("/ws/room-a") as ws:
        ws.send_json({"type": "join", "quiz_id": "room-b", "username": "alice"})
        assert _until(ws, "error")["code"] == "INVALID_MESSAGE"


def test_start_and_answer_require_joining_first() -> None:
    room = "no-join-room"
    with TestClient(main_module.app) as client, client.websocket_connect(f"/ws/{room}") as ws:
        ws.send_json({"type": "start", "quiz_id": room})
        assert _until(ws, "error")["code"] == "UNKNOWN_USER"
        ws.send_json({"type": "answer", "request_id": "r", "question_id": "q0", "choice_index": 0})
        assert _until(ws, "error")["code"] == "UNKNOWN_USER"


def test_a_connection_cannot_join_twice() -> None:
    room = "double-join-room"
    with TestClient(main_module.app) as client, client.websocket_connect(f"/ws/{room}") as ws:
        _join(ws, room, "alice")
        ws.send_json({"type": "join", "quiz_id": room, "username": "alice-2"})
        assert _until(ws, "error")["code"] == "INVALID_MESSAGE"
        assert len(main_module.store._sessions[room].participants) == 1  # noqa: SLF001


def test_malformed_input_gets_typed_errors_and_keeps_the_connection_open() -> None:
    with TestClient(main_module.app) as client, client.websocket_connect("/ws/junk-room") as ws:
        ws.send_text("not json at all")
        assert _until(ws, "error")["code"] == "INVALID_MESSAGE"
        ws.send_json({"type": "definitely-not-a-message"})
        assert _until(ws, "error")["code"] == "INVALID_MESSAGE"
        ws.send_json({"type": "ping"})
        assert _until(ws, "pong")["type"] == "pong"


def test_joining_a_started_quiz_is_rejected() -> None:
    room = "late-room"
    with (
        TestClient(main_module.app) as client,
        client.websocket_connect(f"/ws/{room}") as first,
        client.websocket_connect(f"/ws/{room}") as late,
    ):
        _join(first, room, "alice")
        first.send_json({"type": "start", "quiz_id": room})
        _until(first, "question")
        late.send_json({"type": "join", "quiz_id": room, "username": "bob"})
        assert _until(late, "error")["code"] == "QUIZ_ALREADY_STARTED"


def test_leaderboard_lists_every_player_as_soon_as_a_question_starts() -> None:
    room = "early-board-room"
    with (
        TestClient(main_module.app) as client,
        client.websocket_connect(f"/ws/{room}") as first,
        client.websocket_connect(f"/ws/{room}") as second,
    ):
        _join(first, room, "alice")
        _join(second, room, "bob")
        first.send_json({"type": "start", "quiz_id": room})
        _until(second, "question")
        standings = _until(second, "leaderboard")["standings"]
        assert {entry["username"] for entry in standings} == {"alice", "bob"}
        assert all(entry["score"] == 0 for entry in standings)
