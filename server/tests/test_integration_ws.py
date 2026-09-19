"""End-to-end WebSocket integration test.

Runs the real FastAPI app (no mocks below the WebSocket boundary) with
multiple simultaneous simulated clients, driving a full
join -> start -> answer -> quiz_end flow and asserting the final
leaderboard is correctly ranked. Question duration is monkeypatched down
to a couple hundred milliseconds so the test doesn't wait on the
production 15s-per-question pacing.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.quiz import Question

FAST_QUESTIONS = [
    Question(id="q0", text="Q0?", choices=["a", "b", "c"], correct_index=1, duration_ms=250),
    Question(id="q1", text="Q1?", choices=["a", "b", "c"], correct_index=2, duration_ms=250),
]


def _fast_question_bank() -> list[Question]:
    return list(FAST_QUESTIONS)


@pytest.fixture(autouse=True)
def _use_fast_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "mock_question_bank", _fast_question_bank)


def _receive_until(ws: Any, message_type: str, max_messages: int = 30) -> dict[str, Any]:
    for _ in range(max_messages):
        message = ws.receive_json()
        if message["type"] == message_type:
            return message
    raise AssertionError(f"did not observe a '{message_type}' message within {max_messages} messages")


def test_full_quiz_flow_produces_correctly_ranked_leaderboard() -> None:
    quiz_id = "quiz-integration-1"
    with (
        TestClient(main_module.app) as client,
        client.websocket_connect(f"/ws/{quiz_id}") as alice,
        client.websocket_connect(f"/ws/{quiz_id}") as bob,
        client.websocket_connect(f"/ws/{quiz_id}") as carol,
    ):
        alice.send_json({"type": "join", "quiz_id": quiz_id, "username": "alice"})
        bob.send_json({"type": "join", "quiz_id": quiz_id, "username": "bob"})
        carol.send_json({"type": "join", "quiz_id": quiz_id, "username": "carol"})

        _receive_until(alice, "joined")
        _receive_until(bob, "joined")
        _receive_until(carol, "joined")

        alice.send_json({"type": "start", "quiz_id": quiz_id})

        for question in FAST_QUESTIONS:
            for ws in (alice, bob, carol):
                seen = _receive_until(ws, "question")
                assert seen["question_id"] == question.id

            # alice and bob answer correctly, carol answers incorrectly.
            alice.send_json(
                {
                    "type": "answer",
                    "request_id": f"alice-{question.id}",
                    "question_id": question.id,
                    "choice_index": question.correct_index,
                }
            )
            bob.send_json(
                {
                    "type": "answer",
                    "request_id": f"bob-{question.id}",
                    "question_id": question.id,
                    "choice_index": question.correct_index,
                }
            )
            carol.send_json(
                {
                    "type": "answer",
                    "request_id": f"carol-{question.id}",
                    "question_id": question.id,
                    "choice_index": (question.correct_index + 1) % len(question.choices),
                }
            )

            alice_ack = _receive_until(alice, "score_update")
            bob_ack = _receive_until(bob, "score_update")
            carol_ack = _receive_until(carol, "score_update")
            assert alice_ack["correct"] is True
            assert bob_ack["correct"] is True
            assert carol_ack["correct"] is False

        final = _receive_until(alice, "quiz_end")
        standings = final["final_standings"]

        usernames_by_rank = [entry["username"] for entry in standings]
        assert usernames_by_rank[2] == "carol"  # never scored, always ranked last
        assert usernames_by_rank[0] in {"alice", "bob"}
        assert usernames_by_rank[1] in {"alice", "bob"}
        assert standings[0]["score"] > standings[2]["score"]
        assert standings[2]["score"] == 0
