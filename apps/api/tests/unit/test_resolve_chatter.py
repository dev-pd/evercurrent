from __future__ import annotations

from evercurrent.scripts.resolve_chatter import context_text, resolving_text


def test_decision_resolving_text_clearly_closes() -> None:
    body = resolving_text("decision", "switch to AlumWest")
    assert "switch to AlumWest" in body
    assert "closing" in body.lower()


def test_risk_resolving_text_says_mitigated() -> None:
    body = resolving_text("risk", "thermal margin")
    assert "mitigated" in body.lower()


def test_question_resolving_text_says_answered() -> None:
    body = resolving_text("question", "which alloy")
    assert "answered" in body.lower()


def test_context_text_is_explicitly_not_resolved() -> None:
    body = context_text("thermal margin")
    assert "not resolved" in body.lower()
