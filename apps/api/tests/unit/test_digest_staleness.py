from __future__ import annotations

from evercurrent.api.routes.digests import _compute_is_stale


def test_fresh_when_today_and_nothing_changed() -> None:
    assert (
        _compute_is_stale(
            day_index=5,
            today_index=5,
            resolved_cited=0,
            new_messages=0,
            new_threshold=3,
        )
        is False
    )


def test_stale_when_from_a_previous_day() -> None:
    assert (
        _compute_is_stale(
            day_index=4,
            today_index=5,
            resolved_cited=0,
            new_messages=0,
            new_threshold=3,
        )
        is True
    )


def test_stale_when_a_cited_signal_has_resolved() -> None:
    assert (
        _compute_is_stale(
            day_index=5,
            today_index=5,
            resolved_cited=1,
            new_messages=0,
            new_threshold=3,
        )
        is True
    )


def test_stale_when_enough_new_messages_arrived() -> None:
    assert (
        _compute_is_stale(
            day_index=5,
            today_index=5,
            resolved_cited=0,
            new_messages=3,
            new_threshold=3,
        )
        is True
    )


def test_fresh_when_new_activity_below_threshold() -> None:
    assert (
        _compute_is_stale(
            day_index=5,
            today_index=5,
            resolved_cited=0,
            new_messages=2,
            new_threshold=3,
        )
        is False
    )
