from __future__ import annotations

from evercurrent.eve.grounding import ground_sources


def _evidence(*snippets: str) -> list[dict[str, str]]:
    return [{"snippet": s} for s in snippets]


def test_source_matching_retrieved_evidence_is_kept() -> None:
    evidence = _evidence("REQ-245 raises max gripper torque from 15 Nm to 22 Nm")
    sources = [{"snippet": "gripper torque raised to 22 Nm per REQ-245"}]

    grounded = ground_sources(sources, evidence)

    assert len(grounded) == 1


def test_fabricated_source_with_no_overlap_is_dropped() -> None:
    evidence = _evidence("REQ-245 raises max gripper torque to 22 Nm")
    sources = [{"snippet": "battery pack thermal runaway during charge cycle"}]

    grounded = ground_sources(sources, evidence)

    assert grounded == []


def test_no_evidence_drops_all_sources() -> None:
    sources = [{"snippet": "anything at all here"}]

    grounded = ground_sources(sources, evidence=[])

    assert grounded == []


def test_empty_snippet_is_not_grounded() -> None:
    evidence = _evidence("some real retrieved text about torque")
    sources = [{"snippet": ""}]

    grounded = ground_sources(sources, evidence)

    assert grounded == []


def test_mixed_sources_keep_only_grounded_ones() -> None:
    evidence = _evidence("supplier AlumWest FAI failed on flatness tolerance")
    sources = [
        {"snippet": "AlumWest FAI failed flatness tolerance"},
        {"snippet": "completely unrelated invented claim about firmware"},
    ]

    grounded = ground_sources(sources, evidence)

    assert len(grounded) == 1
    assert "AlumWest" in grounded[0]["snippet"]
