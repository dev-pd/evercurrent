"""The seed chatter generator dedups on a normalized text key so the Sonnet
generator re-emitting a line across rounds doesn't seed duplicate messages."""

from __future__ import annotations

from evercurrent.scripts.demo_chatter import _norm


def test_norm_collapses_case_and_whitespace_so_duplicates_share_a_key() -> None:
    a = "Thermal modeling flagged  junction temps hitting 85C.\n"
    b = "thermal modeling flagged junction temps hitting 85c."
    assert _norm(a) == _norm(b)


def test_norm_keeps_distinct_messages_distinct() -> None:
    assert _norm("Tighten cell spacing on the BRK-A1 rail.") != _norm(
        "Derate the pack to 25A nominal."
    )
