"""Timeline projection — derive a phase/lane schedule from a project's real
fields.

Per-phase and per-subsystem schedules are not persisted. Phase durations come
from a canonical hardware NPI ladder anchored to the project's real
`start_date` and positioned by `current_day`; lanes come from the real
distinct subsystems owned by project members. The projection is pure (no I/O)
so it is unit-tested directly.
"""

from evercurrent.timeline.projection import (
    PHASE_LADDER,
    TOTAL_DAYS,
    build_timeline,
)
from evercurrent.timeline.schemas import (
    Lane,
    LaneSegment,
    PhaseBlock,
    TimelineProjection,
)

__all__ = [
    "PHASE_LADDER",
    "TOTAL_DAYS",
    "Lane",
    "LaneSegment",
    "PhaseBlock",
    "TimelineProjection",
    "build_timeline",
]
