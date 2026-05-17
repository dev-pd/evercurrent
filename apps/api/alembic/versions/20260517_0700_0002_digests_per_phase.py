"""digests indexed by (user_id, day, phase)

Drop the (user_id, day) unique index, add a `phase` column with the
project phase the digest was generated under, and re-introduce
uniqueness over (user_id, day, phase) so every phase variant can be
pre-computed and served instantly.

Revision ID: 0002_digests_per_phase
Revises: 0001_initial_schema
Create Date: 2026-05-17 07:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_digests_per_phase"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "digests",
        sa.Column("phase", sa.String(32), nullable=False, server_default="DVT"),
    )
    op.drop_index("ix_digests_user_day", table_name="digests")
    op.create_index(
        "ix_digests_user_day_phase",
        "digests",
        ["user_id", "day", "phase"],
        unique=True,
    )
    op.alter_column("digests", "phase", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_digests_user_day_phase", table_name="digests")
    op.create_index(
        "ix_digests_user_day",
        "digests",
        ["user_id", "day"],
        unique=True,
    )
    op.drop_column("digests", "phase")
