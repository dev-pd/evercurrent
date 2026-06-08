"""Phase 6: cards + card_sources.

Knowledge Cards are the atomic unit of the product. One Card per
durable decision / risk / question. Sources cite the messages,
document chunks, and PRs the Card was built from.

Idempotency: `triggering_message_id` records the message that caused
the build. A partial unique index on `(triggering_message_id, kind)`
prevents a Celery retry of `build_card` from creating a second Card
for the same trigger. The builder catches `IntegrityError` and
returns the existing row.

RLS: both tables carry `org_id` and the standard tenant-isolation
policy.

Revision ID: 0008_cards
Revises: 0007_scores_table
Create Date: 2026-06-07 23:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_cards"
down_revision: str | None = "0007_scores_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    op.create_table(
        "cards",
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
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="open"),
        sa.Column(
            "owner_membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_memberships.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "triggering_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "affected_subsystems",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("confidence", sa.REAL, nullable=False, server_default="0.5"),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "kind IN ('decision','risk','question')",
            name="ck_cards_kind",
        ),
        sa.CheckConstraint(
            "status IN ('open','resolved','dismissed')",
            name="ck_cards_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_cards_confidence_range",
        ),
    )
    op.create_index("cards_org_idx", "cards", ["org_id"])
    op.create_index("cards_project_kind_idx", "cards", ["project_id", "kind"])
    op.create_index(
        "cards_project_updated_idx",
        "cards",
        ["project_id", sa.text("updated_at DESC")],
    )
    # Idempotency anchor: one Card per (triggering_message, kind).
    op.execute(
        "CREATE UNIQUE INDEX cards_triggering_message_kind_uidx "
        "ON cards (triggering_message_id, kind) "
        "WHERE triggering_message_id IS NOT NULL",
    )
    _enable_rls("cards")

    op.create_table(
        "card_sources",
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
            "card_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.Text, nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "source_kind IN ('message','document_chunk','pr')",
            name="ck_card_sources_kind",
        ),
        sa.UniqueConstraint(
            "card_id",
            "source_kind",
            "source_id",
            name="card_sources_unique",
        ),
    )
    op.create_index("card_sources_card_idx", "card_sources", ["card_id"])
    op.create_index(
        "card_sources_lookup_idx",
        "card_sources",
        ["source_kind", "source_id"],
    )
    _enable_rls("card_sources")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS card_sources_tenant_isolation ON card_sources")
    op.execute("ALTER TABLE card_sources DISABLE ROW LEVEL SECURITY")
    op.drop_index("card_sources_lookup_idx", table_name="card_sources")
    op.drop_index("card_sources_card_idx", table_name="card_sources")
    op.drop_table("card_sources")

    op.execute("DROP POLICY IF EXISTS cards_tenant_isolation ON cards")
    op.execute("ALTER TABLE cards DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS cards_triggering_message_kind_uidx")
    op.drop_index("cards_project_updated_idx", table_name="cards")
    op.drop_index("cards_project_kind_idx", table_name="cards")
    op.drop_index("cards_org_idx", table_name="cards")
    op.drop_table("cards")
