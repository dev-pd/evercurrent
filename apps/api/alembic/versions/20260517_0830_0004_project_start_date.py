"""project.start_date for day <-> calendar date mapping

day N maps to start_date + (N-1) days. `refresh_today` rolls
`current_day` forward whenever wall-clock today advances past it.

Revision ID: 0004_project_start_date
Revises: 0003_doc_phases
Create Date: 2026-05-17 08:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_project_start_date"
down_revision: str | None = "0003_doc_phases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("start_date", sa.Date, nullable=False, server_default="2026-05-11"),
    )
    op.alter_column("projects", "start_date", server_default=None)


def downgrade() -> None:
    op.drop_column("projects", "start_date")
