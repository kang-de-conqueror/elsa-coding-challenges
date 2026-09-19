from app.scoring import RankableParticipant, build_leaderboard, calculate_points


def test_incorrect_answer_scores_zero() -> None:
    assert calculate_points(correct=False, remaining_ms=10_000, duration_ms=15_000) == 0


def test_correct_answer_with_no_time_left_scores_base_only() -> None:
    assert calculate_points(correct=True, remaining_ms=0, duration_ms=15_000) == 1000


def test_correct_answer_with_full_time_left_scores_base_plus_max_bonus() -> None:
    assert calculate_points(correct=True, remaining_ms=15_000, duration_ms=15_000) == 1500


def test_correct_answer_with_half_time_left_scores_half_bonus() -> None:
    assert calculate_points(correct=True, remaining_ms=7_500, duration_ms=15_000) == 1250


def test_negative_remaining_time_is_clamped_to_zero_bonus() -> None:
    # Defensive: submit_answer() already rejects late answers as incorrect,
    # but the scoring function itself must not go negative if ever called
    # directly with an out-of-range value.
    assert calculate_points(correct=True, remaining_ms=-500, duration_ms=15_000) == 1000


def test_remaining_greater_than_duration_is_clamped_to_max_bonus() -> None:
    assert calculate_points(correct=True, remaining_ms=99_999, duration_ms=15_000) == 1500


def _participant(user_id: str, score: int, total_response_ms: int, join_order: int) -> RankableParticipant:
    return RankableParticipant(
        user_id=user_id,
        username=user_id,
        score=score,
        total_response_ms=total_response_ms,
        join_order=join_order,
    )


def test_leaderboard_ranks_by_score_descending() -> None:
    entries = build_leaderboard(
        [
            _participant("a", score=1000, total_response_ms=5000, join_order=0),
            _participant("b", score=2000, total_response_ms=5000, join_order=1),
        ]
    )
    assert [e.user_id for e in entries] == ["b", "a"]
    assert [e.rank for e in entries] == [1, 2]


def test_leaderboard_tie_breaks_on_faster_total_response_time() -> None:
    entries = build_leaderboard(
        [
            _participant("slow", score=1000, total_response_ms=9000, join_order=0),
            _participant("fast", score=1000, total_response_ms=3000, join_order=1),
        ]
    )
    assert [e.user_id for e in entries] == ["fast", "slow"]


def test_leaderboard_final_tie_break_is_join_order() -> None:
    entries = build_leaderboard(
        [
            _participant("second", score=1000, total_response_ms=3000, join_order=1),
            _participant("first", score=1000, total_response_ms=3000, join_order=0),
        ]
    )
    assert [e.user_id for e in entries] == ["first", "second"]
