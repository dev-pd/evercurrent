from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from evercurrent.notify.quiet_hours import is_within_quiet, next_open


def test_within_simple_window() -> None:
    tz = ZoneInfo("UTC")
    now = dt.datetime(2026, 6, 7, 12, 30, tzinfo=dt.UTC)
    assert (
        is_within_quiet(
            now,
            tz=tz,
            quiet_start=dt.time(12, 0),
            quiet_end=dt.time(13, 0),
        )
        is True
    )


def test_within_simple_window_outside() -> None:
    tz = ZoneInfo("UTC")
    now = dt.datetime(2026, 6, 7, 14, 0, tzinfo=dt.UTC)
    assert (
        is_within_quiet(
            now,
            tz=tz,
            quiet_start=dt.time(12, 0),
            quiet_end=dt.time(13, 0),
        )
        is False
    )


def test_within_midnight_wrap_late_evening() -> None:
    tz = ZoneInfo("UTC")
    now = dt.datetime(2026, 6, 7, 23, 0, tzinfo=dt.UTC)
    assert (
        is_within_quiet(
            now,
            tz=tz,
            quiet_start=dt.time(22, 0),
            quiet_end=dt.time(7, 0),
        )
        is True
    )


def test_within_midnight_wrap_early_morning() -> None:
    tz = ZoneInfo("UTC")
    now = dt.datetime(2026, 6, 7, 6, 0, tzinfo=dt.UTC)
    assert (
        is_within_quiet(
            now,
            tz=tz,
            quiet_start=dt.time(22, 0),
            quiet_end=dt.time(7, 0),
        )
        is True
    )


def test_within_midnight_wrap_midday_is_active() -> None:
    tz = ZoneInfo("UTC")
    now = dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC)
    assert (
        is_within_quiet(
            now,
            tz=tz,
            quiet_start=dt.time(22, 0),
            quiet_end=dt.time(7, 0),
        )
        is False
    )


def test_next_open_simple() -> None:
    tz = ZoneInfo("UTC")
    now = dt.datetime(2026, 6, 7, 12, 30, tzinfo=dt.UTC)
    nxt = next_open(now, tz=tz, quiet_end=dt.time(13, 0))
    assert nxt == dt.datetime(2026, 6, 7, 13, 0, tzinfo=dt.UTC)


def test_next_open_midnight_wrap_late_evening() -> None:
    tz = ZoneInfo("UTC")
    now = dt.datetime(2026, 6, 7, 23, 0, tzinfo=dt.UTC)
    nxt = next_open(now, tz=tz, quiet_end=dt.time(7, 0))
    assert nxt == dt.datetime(2026, 6, 8, 7, 0, tzinfo=dt.UTC)


def test_next_open_midnight_wrap_early_morning() -> None:
    tz = ZoneInfo("UTC")
    now = dt.datetime(2026, 6, 7, 6, 0, tzinfo=dt.UTC)
    nxt = next_open(now, tz=tz, quiet_end=dt.time(7, 0))
    assert nxt == dt.datetime(2026, 6, 7, 7, 0, tzinfo=dt.UTC)


def test_respects_user_timezone_la_vs_kolkata() -> None:
    la = ZoneInfo("America/Los_Angeles")
    kolkata = ZoneInfo("Asia/Kolkata")
    start = dt.time(22, 0)
    end = dt.time(7, 0)

    instant_a = dt.datetime(2026, 6, 7, 4, 0, tzinfo=dt.UTC)
    assert is_within_quiet(instant_a, tz=la, quiet_start=start, quiet_end=end) is False
    assert (
        is_within_quiet(
            instant_a,
            tz=kolkata,
            quiet_start=start,
            quiet_end=end,
        )
        is False
    )

    instant_b = dt.datetime(2026, 6, 7, 6, 0, tzinfo=dt.UTC)
    assert is_within_quiet(instant_b, tz=la, quiet_start=start, quiet_end=end) is True
    assert (
        is_within_quiet(
            instant_b,
            tz=kolkata,
            quiet_start=start,
            quiet_end=end,
        )
        is False
    )
