"""Phase 17: drop the unused `feedback` table.

The card 👍/👎 feedback feature was never wired into the UI and the route that
would have written this table only bumped `topic_weights` — nothing ever
inserted or read `feedback`. Removing the dead table + its model.

Revision ID: 0016_drop_feedback
Revises: 0015_org_branding
Create Date: 2026-06-16 22:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_drop_feedback"
down_revision = "0015_org_branding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("feedback")


def downgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("signal IN (-1, 1)", name="ck_feedback_signal"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_message_id", "feedback", ["message_id"])
