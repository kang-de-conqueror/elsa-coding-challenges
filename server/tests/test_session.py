import asyncio

import pytest

from app.quiz import Question, QuizError, QuizSession, QuizState


def _questions(count: int = 2, duration_ms: int = 10_000) -> list[Question]:
    return [
        Question(
            id=f"q{i}",
            text=f"Question {i}",
            choices=["a", "b", "c"],
            correct_index=1,
            duration_ms=duration_ms,
        )
        for i in range(count)
    ]


async def test_join_in_lobby_succeeds() -> None:
    session = QuizSession("quiz-1", _questions())
    alice = await session.join("alice")
    bob = await session.join("bob")
    assert {alice.username, bob.username} == {"alice", "bob"}
    assert alice.user_id != bob.user_id


async def test_join_with_duplicate_username_is_rejected() -> None:
    session = QuizSession("quiz-1", _questions())
    await session.join("alice")
    with pytest.raises(QuizError) as exc_info:
        await session.join("alice")
    assert exc_info.value.code == "DUPLICATE_USERNAME"


async def test_join_after_start_is_rejected() -> None:
    session = QuizSession("quiz-1", _questions())
    await session.join("alice")
    await session.start()
    with pytest.raises(QuizError) as exc_info:
        await session.join("bob")
    assert exc_info.value.code == "QUIZ_ALREADY_STARTED"


async def test_start_twice_is_rejected() -> None:
    session = QuizSession("quiz-1", _questions())
    await session.join("alice")
    await session.start()
    with pytest.raises(QuizError) as exc_info:
        await session.start()
    assert exc_info.value.code == "QUIZ_ALREADY_STARTED"


async def test_advance_question_walks_through_all_questions_then_finishes() -> None:
    session = QuizSession("quiz-1", _questions(count=2))
    first = await session.start()
    assert first.id == "q0"
    assert session.state == QuizState.IN_PROGRESS

    second = await session.advance_question()
    assert second is not None
    assert second.id == "q1"

    third = await session.advance_question()
    assert third is None
    assert session.state == QuizState.FINISHED


async def test_answer_for_stale_question_is_rejected() -> None:
    session = QuizSession("quiz-1", _questions(count=2))
    alice = await session.join("alice")
    await session.start()
    await session.advance_question()  # now on q1, q0 is stale

    with pytest.raises(QuizError) as exc_info:
        await session.submit_answer(user_id=alice.user_id, question_id="q0", choice_index=1, request_id="r1")
    assert exc_info.value.code == "NO_ACTIVE_QUESTION"


async def test_rejoin_unknown_user_is_rejected() -> None:
    session = QuizSession("quiz-1", _questions())
    with pytest.raises(QuizError) as exc_info:
        await session.rejoin("does-not-exist")
    assert exc_info.value.code == "UNKNOWN_USER"


async def test_rejoin_restores_connected_flag() -> None:
    session = QuizSession("quiz-1", _questions())
    alice = await session.join("alice")
    session.mark_disconnected(alice.user_id)
    assert session.participants[alice.user_id].connected is False

    rejoined = await session.rejoin(alice.user_id)
    assert rejoined.connected is True


async def test_correct_answer_awards_points_and_updates_leaderboard() -> None:
    session = QuizSession("quiz-1", _questions())
    alice = await session.join("alice")
    question = await session.start()

    result = await session.submit_answer(
        user_id=alice.user_id, question_id=question.id, choice_index=question.correct_index, request_id="r1"
    )
    assert result.correct is True
    assert result.points_awarded > 0
    assert result.total_score == result.points_awarded

    leaderboard = session.leaderboard()
    assert leaderboard[0].user_id == alice.user_id
    assert leaderboard[0].score == result.points_awarded


async def test_duplicate_request_id_does_not_double_score() -> None:
    session = QuizSession("quiz-1", _questions())
    alice = await session.join("alice")
    question = await session.start()

    first = await session.submit_answer(
        user_id=alice.user_id,
        question_id=question.id,
        choice_index=question.correct_index,
        request_id="same-id",
    )
    second = await session.submit_answer(
        user_id=alice.user_id,
        question_id=question.id,
        choice_index=question.correct_index,
        request_id="same-id",
    )

    assert second.duplicate is True
    assert second.total_score == first.total_score
    assert session.participants[alice.user_id].score == first.points_awarded


async def test_answering_same_question_twice_with_different_request_id_does_not_double_score() -> None:
    session = QuizSession("quiz-1", _questions())
    alice = await session.join("alice")
    question = await session.start()

    first = await session.submit_answer(
        user_id=alice.user_id, question_id=question.id, choice_index=question.correct_index, request_id="r1"
    )
    second = await session.submit_answer(
        user_id=alice.user_id, question_id=question.id, choice_index=question.correct_index, request_id="r2"
    )

    assert second.duplicate is True
    assert session.participants[alice.user_id].score == first.points_awarded


async def test_concurrent_answers_from_many_participants_never_corrupt_state() -> None:
    """asyncio.gather submits N answers "simultaneously" (interleaved at
    await points within a single event loop tick). Without the per-session
    lock in QuizSession, this can lose updates; with it, every participant's
    score must land exactly once.
    """

    session = QuizSession("quiz-1", _questions())
    participants = await asyncio.gather(*(session.join(f"user{i}") for i in range(50)))
    question = await session.start()

    results = await asyncio.gather(
        *(
            session.submit_answer(
                user_id=p.user_id,
                question_id=question.id,
                choice_index=question.correct_index,
                request_id=f"req-{p.user_id}",
            )
            for p in participants
        )
    )

    assert all(r.correct for r in results)
    assert all(r.points_awarded > 0 for r in results)
    scores = {p.user_id: p.score for p in session.participants.values()}
    assert all(score == results[0].points_awarded for score in scores.values())
    assert len(session.leaderboard()) == 50
