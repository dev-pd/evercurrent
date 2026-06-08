"""Phase 3: connectors + raw_events + multi-tenant messages.

Adds the data plumbing for Slack ingest:

- `connectors`: one row per (org, kind) install. Holds the encrypted
  bot token in `credentials_secret`.
- `connector_channels`: which channels we know about per connector;
  `ingest` boolean toggles whether webhook events for the channel
  are persisted.
- `raw_events`: untouched webhook payload, keyed by
  `(source, external_id)` for free dedupe.
- `messages`: drops the Phase 1 single-tenant shape and recreates it
  with the multi-tenant SYSTEM_DESIGN §2.3 shape (`source`,
  `external_id`, `thread_root_id`, `org_id`, free-text `channel`).
  `(source, external_id)` is the load-bearing dedupe key — the
  webhook handler relies on its uniqueness for idempotency.
- `message_tags`: rebuilt to match the new `messages` PK.

The Phase 1 `messages`/`message_tags` schema referenced
`projects`/`channels`/`users` foreign keys that don't fit the
multi-source connector model. We drop and recreate rather than try
to migrate — there's no production data yet, and the take-home
explicitly accepts this kind of squash inside the build window.

Revision ID: 0006_connectors_and_raw_events
Revises: 0005_orgs_and_rls
Create Date: 2026-06-07 21:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_connectors_and_raw_events"
down_revision: str | None = "0005_orgs_and_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    """Enable RLS + tenant-isolation policy on a tenant-scoped table."""
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
    # 1. Drop the Phase 1 single-tenant message_tags + messages so we can
    # recreate them with the multi-tenant connector-aware shape.
    op.execute("DROP POLICY IF EXISTS message_tags_tenant_isolation ON message_tags")
    op.execute("DROP POLICY IF EXISTS messages_tenant_isolation ON messages")
    op.execute("DROP TABLE IF EXISTS message_tags CASCADE")
    op.execute("DROP TABLE IF EXISTS messages CASCADE")

    # 2. Connectors: one row per (org, kind). Token blob is Fernet-encrypted
    # by the application before insert; DB sees opaque text.
    op.create_table(
        "connectors",
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
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("external_team_id", sa.Text, nullable=True),
        sa.Column("credentials_secret", sa.Text, nullable=False),
        sa.Column(
            "installed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_memberships.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "installed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("org_id", "kind", name="connectors_org_kind_unique"),
    )
    op.create_index("connectors_org_idx", "connectors", ["org_id"])
    # Webhook handler looks up the connector by team_id with no user context,
    # so this needs to be fast and unique-per-source.
    op.create_index(
        "connectors_team_lookup_idx",
        "connectors",
        ["kind", "external_team_id"],
    )
    _enable_rls("connectors")

    # 3. Connector channels: rows discovered from conversations.list, plus
    # the toggle that decides whether webhook events for the channel are
    # persisted.
    op.create_table(
        "connector_channels",
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
            "connector_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("ingest", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "connector_id",
            "external_id",
            name="connector_channels_unique",
        ),
    )
    op.create_index(
        "connector_channels_connector_idx",
        "connector_channels",
        ["connector_id"],
    )
    _enable_rls("connector_channels")

    # 4. Raw events: the untouched webhook payload. Unique constraint on
    # (source, external_id) is load-bearing — the Slack webhook relies
    # on its uniqueness for dedupe so we never persist the same event
    # twice when Slack retries.
    op.create_table(
        "raw_events",
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
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("source", "external_id", name="raw_events_dedupe_unique"),
    )
    op.create_index("raw_events_org_idx", "raw_events", ["org_id"])
    op.create_index(
        "raw_events_received_idx",
        "raw_events",
        ["received_at"],
    )
    _enable_rls("raw_events")

    # 5. Messages: new multi-tenant connector-aware shape. `(source,
    # external_id)` is the dedupe key the orphan-reply fetch path
    # relies on when a webhook race could otherwise insert the parent
    # twice.
    op.create_table(
        "messages",
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
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("channel", sa.Text, nullable=True),
        sa.Column(
            "thread_root_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "author_membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_memberships.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("author_display_name", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("posted_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("source", "external_id", name="messages_dedupe_unique"),
    )
    op.create_index("messages_org_idx", "messages", ["org_id"])
    op.create_index(
        "messages_org_posted_idx",
        "messages",
        ["org_id", sa.text("posted_at DESC")],
    )
    op.create_index(
        "messages_project_posted_idx",
        "messages",
        ["project_id", sa.text("posted_at DESC")],
    )
    op.create_index(
        "messages_thread_root_idx",
        "messages",
        ["thread_root_id"],
    )
    _enable_rls("messages")

    # 6. Message tags: rebuilt to point at the new messages PK.
    op.create_table(
        "message_tags",
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
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.Text, nullable=True),
        sa.Column("urgency", sa.Text, nullable=True),
        sa.Column(
            "entities",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "affected_roles",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "tagged_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("tagged_by_model", sa.Text, nullable=False),
        sa.UniqueConstraint("message_id", name="message_tags_message_unique"),
    )
    op.create_index("message_tags_org_idx", "message_tags", ["org_id"])
    op.create_index("message_tags_topic_idx", "message_tags", ["topic"])
    _enable_rls("message_tags")


def downgrade() -> None:
    for table in (
        "message_tags",
        "messages",
        "raw_events",
        "connector_channels",
        "connectors",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
