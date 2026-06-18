"""Spread ingested Slack messages across the project timeline + phases.

Run AFTER connecting Slack and hitting Sync (so backfill has ingested the
corpus). Slack stamped everything 'now'; this rewrites messages.posted_at to a
realistic 16-week spread, in the same order they were posted (which was phase
order EVT -> FCS), so content phase lines up with date phase. Also sets the
project's start_date, current_phase, and phase_concerns to match.

Run:  docker compose exec api python /tmp/backdate_corpus.py
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json

from sqlalchemy import text

from evercurrent.db.session import admin_session_scope

WEEKS = 16
PHASE_CONCERNS = {
    "evt": ["bring-up", "schematic", "first-light", "DFM"],
    "dvt": ["reliability", "test", "thermal", "margin"],
    "pvt": ["yield", "process", "build-readiness", "tooling"],
    "fcs": ["ramp", "field", "RMA", "sustaining"],
}


async def main() -> None:
    async with admin_session_scope() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id FROM messages WHERE source = 'slack' ORDER BY external_id ASC",
                ),
            )
        ).all()
        n = len(rows)
        if n == 0:
            raise SystemExit("no slack messages — connect + Sync first")

        now = dt.datetime.now(dt.UTC)
        span = dt.timedelta(weeks=WEEKS)
        start = now - span
        for rank, (mid,) in enumerate(rows):
            frac = rank / max(1, n - 1)
            posted_at = start + span * frac
            await session.execute(
                text("UPDATE messages SET posted_at = :ts WHERE id = :id"),
                {"ts": posted_at, "id": str(mid)},
            )

        start_date = start.date()
        await session.execute(
            text(
                "UPDATE projects SET start_date = :sd, current_phase = 'fcs', "
                "current_day = :cd, phase_concerns = CAST(:pc AS jsonb)",
            ),
            {
                "sd": start_date,
                "cd": (now.date() - start_date).days,
                "pc": json.dumps(PHASE_CONCERNS),
            },
        )
        await session.commit()
    print(f"backdated {n} messages across {WEEKS} weeks; project start={start_date}, phase=fcs")


if __name__ == "__main__":
    asyncio.run(main())
