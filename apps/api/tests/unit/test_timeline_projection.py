"""Unit tests for the deterministic timeline projection."""

from __future__ import annotations

import datetime as dt
import math
import uuid

from evercurrent.timeline import PHASE_LADDER, TOTAL_DAYS, build_timeline

PROJECT_ID = uuid.uuid4()
START = dt.date(2026, 1, 1)


def _project(current_day: int = 42, phase: str = "DVT", subsystems=("chassis", "power")):
    return build_timeline(
        project_id=PROJECT_ID,
        project_name="Atlas",
        current_phase=phase,
        current_day=current_day,
        start_date=START,
        subsystems=list(subsystems),
    )


def test_total_days_is_sum_of_ladder_durations() -> None:
    assert sum(days for _, days in PHASE_LADDER) == TOTAL_DAYS


def test_phases_cover_every_ladder_entry() -> None:
    proj = _project()
    assert [p.label for p in proj.phases] == [label for label, _ in PHASE_LADDER]


def test_completed_phase_is_marked_done() -> None:
    proj = _project(current_day=42)
    evt = next(p for p in proj.phases if p.label == "EVT")
    assert evt.status == "done"


def test_phase_containing_current_day_is_active() -> None:
    proj = _project(current_day=42)
    dvt = next(p for p in proj.phases if p.label == "DVT")
    assert dvt.status == "active"


def test_future_phase_is_upcoming() -> None:
    proj = _project(current_day=42)
    mp = next(p for p in proj.phases if p.label == "MP")
    assert mp.status == "upcoming"


def test_one_lane_per_subsystem() -> None:
    proj = _project(subsystems=("chassis", "power", "firmware"))
    assert [lane.name for lane in proj.lanes] == ["chassis", "firmware", "power"]


def test_lane_marker_tracks_current_day() -> None:
    proj = _project(current_day=60)
    assert proj.lanes[0].marker == 60 / 30


def test_progress_pct_is_day_fraction_of_plan() -> None:
    proj = _project(current_day=42)
    assert proj.progress_pct == round(42 / TOTAL_DAYS * 100)


def test_month_labels_span_the_whole_plan() -> None:
    proj = _project()
    assert len(proj.months) == math.ceil(TOTAL_DAYS / 30)


def test_fcs_label_dates_to_plan_end() -> None:
    proj = _project()
    expected = (START + dt.timedelta(days=TOTAL_DAYS)).strftime("%b %d")
    assert expected in proj.fcs_label
