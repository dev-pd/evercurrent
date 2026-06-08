"""Pure quiet-hour math.

No I/O. Caller passes a UTC `datetime`, a `ZoneInfo`, and the local
`quiet_start` / `quiet_end` `time` values; we return a bool plus the
next UTC instant outside the quiet window.

The wrap case (e.g. 22:00 → 07:00 spans midnight) is handled by
checking `now >= start or now < end` instead of the simple between.
DST transitions are delegated to `zoneinfo` — never compute UTC offsets
by hand.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo


def _to_local(now: dt.datetime, tz: ZoneInfo) -> dt.datetime:
    if now.tzinfo is None:
        # Caller fault if this happens, but we don't want a silent UTC
        # assumption — fail loud.
        raise ValueError("quiet_hours requires a timezone-aware datetime")
    return now.astimezone(tz)


def is_within_quiet(
    now: dt.datetime,
    *,
    tz: ZoneInfo,
    quiet_start: dt.time,
    quiet_end: dt.time,
) -> bool:
    """Return True iff `now` falls inside `[quiet_start, quiet_end)` local time.

    Wrap-aware: when `quiet_start > quiet_end` the window spans midnight,
    so a local time at or after start OR before end is quiet.
    """
    local_t = _to_local(now, tz).time()
    if quiet_start == quiet_end:
        # Degenerate "no quiet hours" window.
        return False
    if quiet_start < quiet_end:
        return quiet_start <= local_t < quiet_end
    return local_t >= quiet_start or local_t < quiet_end


def next_open(
    now: dt.datetime,
    *,
    tz: ZoneInfo,
    quiet_end: dt.time,
) -> dt.datetime:
    """Return the next UTC instant when the local clock hits `quiet_end`.

    Used to compute Celery `eta=...` when we defer a delivery. The
    caller is responsible for adding jitter on top to avoid the wake-up
    thundering herd at 07:00 local.
    """
    local_now = _to_local(now, tz)
    candidate_local = local_now.replace(
        hour=quiet_end.hour,
        minute=quiet_end.minute,
        second=quiet_end.second,
        microsecond=quiet_end.microsecond,
    )
    if candidate_local <= local_now:
        candidate_local = candidate_local + dt.timedelta(days=1)
    return candidate_local.astimezone(dt.UTC)
