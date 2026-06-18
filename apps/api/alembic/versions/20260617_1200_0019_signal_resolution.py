"""Phase 19: give signals a resolution write-side.

Adds `resolved_at` (stamped when a signal flips to resolved, cleared on
reopen) and `resolving_message_id` (the in-thread message that closed it,
SET NULL if that message is deleted). Until now signals were created `open`
and never closed; these columns back the auto-resolution path.

Revision ID: 0019_signal_resolution
Revises: 0018_rename_cards_to_signals
Create Date: 2026-06-17 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019_signal_resolution"
down_revision = "0018_rename_cards_to_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "signals",
        sa.Column(
            "resolving_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("signals", "resolving_message_id")
    op.drop_column("signals", "resolved_at")
