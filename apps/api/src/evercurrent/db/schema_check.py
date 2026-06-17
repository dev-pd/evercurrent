"""ORM/schema drift check.

Every SQLAlchemy model column must exist in its migrated table — a model that
claims a column the table lacks silently breaks `select(Model)`. Used by the
`make check-models` target and the integration test. Run against a migrated DB.
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from evercurrent.db import models


async def find_drift(conn: AsyncConnection) -> dict[str, list[str]]:
    """Return {table: [model-only columns]} for any table whose model claims
    columns the DB lacks (or "*MISSING TABLE*" if the table is absent)."""
    drift: dict[str, list[str]] = {}
    for table in models.metadata.tables.values():
        rows = (
            await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = :t",
                ),
                {"t": table.name},
            )
        ).scalars().all()
        db_cols = set(rows)
        if not db_cols:
            drift[table.name] = ["*MISSING TABLE*"]
            continue
        model_only = sorted({c.name for c in table.columns} - db_cols)
        if model_only:
            drift[table.name] = model_only
    return drift


async def _run() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            drift = await find_drift(conn)
    finally:
        await engine.dispose()
    if drift:
        print(f"ORM/schema DRIFT: {drift}", file=sys.stderr)
        return 1
    print("OK: all models match the migrated schema")
    return 0


def main() -> None:
    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
