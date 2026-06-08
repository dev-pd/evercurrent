"""Phase 11: subscriptions + notifications tables.

Both tables hang off `org_memberships` (and through it, `orgs`) so RLS
flows the same way the Phase 5 policies set up: every row carries
`org_id` explicitly, the standard tenant-isolation policy filters reads
to the current org context.

`subscriptions` records what the user opted into:
- one row per (membership, kind, value) — `value` is NULL for the
  simple kinds and carries discriminators like `override_quiet` or a
  subsystem name for the parameterised kinds.
- `enabled` toggles without losing the row so we keep auditability.

`notifications` is the append-only log of every send (success, skip, or
fail). The dashboard's "did I get the digest?" lookup hits this table,
and the opened/clicked nullable columns wire up to future click-tracking
without a schema change.

Revision ID: 0011_notifications_subscriptions
Revises: 0010_digests_v2
Create Date: 2026-06-08 02:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_notifications_subscriptions"
down_revision: str | None = "0010_digests_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    # NULL values would collide on the UNIQUE under default semantics, so
    # we coalesce to an empty string for dedupe purposes via a partial
    # expression index.
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


def downgrade() -> None:
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
