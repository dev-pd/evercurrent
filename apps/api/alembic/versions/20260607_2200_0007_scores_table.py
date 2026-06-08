"""Phase 7: scores table.

One row per (project_member, message). Score is precomputed by the
scoring engine after the router tags a message; the dashboard reads
top-N by score for the current member. `reasons` stores the per-signal
breakdown for audit and the "why is this in my top 5" surface.

Revision ID: 0007_scores_table
Revises: 0006_connectors_and_raw_events
Create Date: 2026-06-07 22:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_scores_table"
down_revision: str | None = "0006_connectors_and_raw_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scores",
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
        sa.Column(
            "project_member_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("reasons", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "computed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "project_member_id",
            "message_id",
            name="ix_scores_project_member_message_unique",
        ),
    )
    op.create_index(
        "ix_scores_member_score_desc",
        "scores",
        ["project_member_id", "score"],
    )
    op.create_index("ix_scores_org", "scores", ["org_id"])

    op.execute("ALTER TABLE scores ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY scores_tenant_isolation ON scores
        USING (
            org_id::text = COALESCE(
                current_setting('app.current_org_id', true),
                ''
            )
            OR COALESCE(current_setting('app.current_org_id', true), '') = ''
        )
        """,
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS scores_tenant_isolation ON scores")
    op.execute("ALTER TABLE scores DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_scores_org", table_name="scores")
    op.drop_index("ix_scores_member_score_desc", table_name="scores")
    op.drop_table("scores")
