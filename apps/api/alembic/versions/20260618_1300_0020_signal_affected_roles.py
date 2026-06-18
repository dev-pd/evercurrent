"""Phase 20: add affected_roles to signals for role-based relevance.

The classifier already tags each message with affected_roles (e.g. a message
addressed to "Supply" gets {supply}); carry that onto the signal so the digest
can route by role — a member whose eng_role matches is a guaranteed include,
not contingent on subsystem-tag overlap.

Revision ID: 0020_signal_affected_roles
Revises: 0019_signal_resolution
Create Date: 2026-06-18 13:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020_signal_affected_roles"
down_revision = "0019_signal_resolution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column(
            "affected_roles",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("signals", "affected_roles")
