from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo


def _to_local(now: dt.datetime, tz: ZoneInfo) -> dt.datetime:
    if now.tzinfo is None:
        raise ValueError("quiet_hours requires a timezone-aware datetime")
    return now.astimezone(tz)


def is_within_quiet(
    now: dt.datetime,
    *,
    tz: ZoneInfo,
    quiet_start: dt.time,
    quiet_end: dt.time,
) -> bool:
    local_t = _to_local(now, tz).time()
    if quiet_start == quiet_end:
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
