"""Guard against ORM/schema drift — every model column must exist in its
migrated table. Runs against a migrated DB (CI applies `alembic upgrade head`
first; locally use `make check-models`). Skips if DATABASE_URL isn't set.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from evercurrent.db.schema_check import find_drift


@pytest.mark.asyncio
async def test_models_match_migrated_schema() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            drift = await find_drift(conn)
    finally:
        await engine.dispose()

    assert not drift, f"ORM/schema drift: {drift}"
