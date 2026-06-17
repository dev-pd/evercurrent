"""Phase 17: drop the unused `notifications` + `subscriptions` tables.

The notify subsystem (Slack DM delivery, quiet hours, subscription
preferences) was built but never wired: no Celery task ever enqueued
`deliver_digest_dm`/`deliver_urgent_dm`, no beat schedule referenced them,
and the `/subscriptions` route was never called from the UI. Removing the
dead module, tasks, route, and these two tables.

Revision ID: 0017_drop_notify_tables
Revises: 0016_drop_feedback
Create Date: 2026-06-17 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017_drop_notify_tables"
down_revision = "0016_drop_feedback"
branch_labels = None
depends_on = None


_SUBSCRIPTION_KINDS = (
    "morning_digest",
    "urgent_immediate",
    "weekly_summary",
    "mention",
    "decision_affecting_subsystem",
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
        USING (
            org_id::text = COALESCE(
                current_setting('app.current_org_id', true),
                ''
            )
            OR COALESCE(current_setting('app.current_org_id', true), '') = ''
        )
        """,
    )


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS notifications_tenant_isolation ON notifications")
    op.execute("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY")
    op.drop_index("notifications_org_idx", table_name="notifications")
    op.drop_index("notifications_membership_sent_idx", table_name="notifications")
    op.drop_table("notifications")

    op.execute("DROP POLICY IF EXISTS subscriptions_tenant_isolation ON subscriptions")
    op.execute("ALTER TABLE subscriptions DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS subscriptions_unique")
    op.drop_index("subscriptions_membership_idx", table_name="subscriptions")
    op.drop_table("subscriptions")


def downgrade() -> None:
    kinds_sql = ",".join(f"'{k}'" for k in _SUBSCRIPTION_KINDS)

    op.create_table(
        "subscriptions",
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
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"kind IN ({kinds_sql})",
            name="ck_subscriptions_kind",
        ),
    )
    op.create_index(
        "subscriptions_membership_idx",
        "subscriptions",
        ["membership_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX subscriptions_unique "
        "ON subscriptions (membership_id, kind, COALESCE(value, ''))",
    )
    _enable_rls("subscriptions")

    op.create_table(
        "notifications",
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
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("channel", sa.Text, nullable=False),
        sa.Column(
            "sent_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("clicked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "notifications_membership_sent_idx",
        "notifications",
        ["membership_id", sa.text("sent_at DESC")],
    )
    op.create_index("notifications_org_idx", "notifications", ["org_id"])
    _enable_rls("notifications")
