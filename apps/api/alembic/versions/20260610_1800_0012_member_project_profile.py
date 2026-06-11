"""Phase 13: member project profile — eng role, owned subsystems, topic weights.

Personalization needs per-member engineering context, but `org_memberships`
only carried the org `role` (admin/member) + timezone. The digest + scoring
pipeline hardcoded `owned_subsystems=[]` / `topic_weights={}` because there was
nowhere to read them. This adds the three columns the design doc parked on a
future `project_members` link table — we inline them on `org_memberships`
instead, which is sufficient for the single-project model and keeps RLS simple
(the row already carries `org_id`).

- `eng_role`: the engineering function (mechanical, electrical, supply_chain,
  qa, firmware, em, pm) used by scoring's role-match. Distinct from the
  admin/member `role`. Nullable — members without one fall back to `role`.
- `owned_subsystems`: text[] of subsystems the member owns (chassis, power…).
- `topic_weights`: jsonb the feedback loop bumps over time.

Revision ID: 0012_member_project_profile
Revises: 0011_notifications_subscriptions
Create Date: 2026-06-10 18:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012_member_project_profile"
down_revision = "0011_notifications_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "org_memberships",
        sa.Column("eng_role", sa.Text(), nullable=True),
    )
    op.add_column(
        "org_memberships",
        sa.Column(
            "owned_subsystems",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "org_memberships",
        sa.Column(
            "topic_weights",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("org_memberships", "topic_weights")
    op.drop_column("org_memberships", "owned_subsystems")
    op.drop_column("org_memberships", "eng_role")
