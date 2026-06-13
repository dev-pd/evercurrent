"""Phase 14: insights table — stores Eve agent output.

Eve (the proactive cross-team agent) emits a structured ProactiveInsight; we
persist it as JSONB so the dashboard rail + insights page can read it and so a
run is reproducible. Org-scoped like everything else (RLS).

Revision ID: 0013_insights
Revises: 0012_member_project_profile
Create Date: 2026-06-12 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_insights"
down_revision = "0012_member_project_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insights",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Index("insights_org_idx", "org_id"),
    )


def downgrade() -> None:
    op.drop_table("insights")
