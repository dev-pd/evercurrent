"""Projects a project's start date + current phase onto the fixed phase ladder,
producing the dated phase blocks and lane segments the timeline view renders."""

from __future__ import annotations

import datetime as dt
import math
import uuid

from evercurrent.timeline.schemas import (
    Lane,
    LaneSegment,
    PhaseBlock,
    PhaseStatus,
    TimelineProjection,
)

PHASE_LADDER: tuple[tuple[str, int], ...] = (
    ("EVT", 30),
    ("DVT", 45),
    ("PVT", 30),
    ("MP", 30),
)

DAYS_PER_MONTH = 30
TOTAL_DAYS = sum(days for _, days in PHASE_LADDER)
TOTAL_MONTHS = TOTAL_DAYS / DAYS_PER_MONTH


def _phase_windows() -> list[tuple[str, int, int]]:
    windows: list[tuple[str, int, int]] = []
    cursor = 0
    for label, days in PHASE_LADDER:
        windows.append((label, cursor, cursor + days))
        cursor += days
    return windows


def _phase_status(start_day: int, end_day: int, current_day: int) -> PhaseStatus:
    if end_day <= current_day:
        return "done"
    if start_day <= current_day < end_day:
        return "active"
    return "upcoming"


def _build_phases(current_day: int) -> list[PhaseBlock]:
    return [
        PhaseBlock(
            label=label,
            start_month=start_day / DAYS_PER_MONTH,
            end_month=end_day / DAYS_PER_MONTH,
            status=_phase_status(start_day, end_day, current_day),
        )
        for label, start_day, end_day in _phase_windows()
    ]


def _month_labels(start_date: dt.date) -> list[str]:
    count = math.ceil(TOTAL_MONTHS)
    return [
        (start_date + dt.timedelta(days=i * DAYS_PER_MONTH)).strftime("%b") for i in range(count)
    ]


def _build_lanes(subsystems: list[str], current_day: int) -> list[Lane]:
    marker = current_day / DAYS_PER_MONTH
    done = min(marker, TOTAL_MONTHS)
    lanes: list[Lane] = []
    for name in sorted(set(subsystems)):
        segments = [LaneSegment(start=0.0, end=done, tone="primary")]
        if done < TOTAL_MONTHS:
            segments.append(LaneSegment(start=done, end=TOTAL_MONTHS, tone="muted"))
        lanes.append(Lane(name=name, segments=segments, marker=marker))
    return lanes


def _summary(project_name: str, current_phase: str, progress_pct: int) -> str:
    return (
        f"{project_name} is in {current_phase}. ~{progress_pct}% through the planned NPI schedule."
    )


def build_timeline(
    *,
    project_id: uuid.UUID,
    project_name: str,
    current_phase: str,
    current_day: int,
    start_date: dt.date,
    subsystems: list[str],
) -> TimelineProjection:
    progress_pct = round(current_day / TOTAL_DAYS * 100)
    fcs_date = start_date + dt.timedelta(days=TOTAL_DAYS)
    fcs_label = f"{fcs_date.strftime('%b %d')} FCS · {progress_pct}% complete"
    return TimelineProjection(
        project_id=project_id,
        project_name=project_name,
        current_phase=current_phase,
        current_day=current_day,
        start_date=start_date.isoformat(),
        months=_month_labels(start_date),
        phases=_build_phases(current_day),
        lanes=_build_lanes(subsystems, current_day),
        summary=_summary(project_name, current_phase, progress_pct),
        fcs_label=fcs_label,
        progress_pct=progress_pct,
    )
