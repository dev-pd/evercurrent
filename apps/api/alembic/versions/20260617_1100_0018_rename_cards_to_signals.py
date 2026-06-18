"""Phase 18: rename the `cards` domain concept to `signals`.

Renames the tables (`cards`->`signals`, `card_sources`->`signal_sources`),
the FK column (`signal_sources.card_id`->`signal_id`), the digests citation
column (`digests.card_ids`->`signal_ids`), every `card*` index, and the
tenant-isolation policy names. Enum *values* (kind, status, source kind) are
unchanged — this is purely a concept rename.

`ALTER TABLE ... RENAME` preserves RLS policies, constraints, and indexes
attached to the table; we only rename the objects whose *names* embed "card"
so the schema reads coherently.

Revision ID: 0018_rename_cards_to_signals
Revises: 0017_drop_notify_tables
Create Date: 2026-06-17 11:00:00
"""

from __future__ import annotations

from alembic import op

revision = "0018_rename_cards_to_signals"
down_revision = "0017_drop_notify_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE cards RENAME TO signals")
    op.execute("ALTER TABLE card_sources RENAME TO signal_sources")
    op.execute("ALTER TABLE signal_sources RENAME COLUMN card_id TO signal_id")
    op.execute("ALTER TABLE digests RENAME COLUMN card_ids TO signal_ids")

    op.execute("ALTER INDEX cards_org_idx RENAME TO signals_org_idx")
    op.execute("ALTER INDEX cards_project_kind_idx RENAME TO signals_project_kind_idx")
    op.execute("ALTER INDEX cards_project_updated_idx RENAME TO signals_project_updated_idx")
    op.execute(
        "ALTER INDEX cards_triggering_message_kind_uidx "
        "RENAME TO signals_triggering_message_kind_uidx",
    )
    op.execute("ALTER INDEX card_sources_card_idx RENAME TO signal_sources_signal_idx")
    op.execute("ALTER INDEX card_sources_lookup_idx RENAME TO signal_sources_lookup_idx")
    op.execute("ALTER INDEX card_sources_unique RENAME TO signal_sources_unique")

    op.execute("ALTER POLICY cards_tenant_isolation ON signals RENAME TO signals_tenant_isolation")
    op.execute(
        "ALTER POLICY card_sources_tenant_isolation ON signal_sources "
        "RENAME TO signal_sources_tenant_isolation",
    )


def downgrade() -> None:
    op.execute(
        "ALTER POLICY signal_sources_tenant_isolation ON signal_sources "
        "RENAME TO card_sources_tenant_isolation",
    )
    op.execute("ALTER POLICY signals_tenant_isolation ON signals RENAME TO cards_tenant_isolation")

    op.execute("ALTER INDEX signal_sources_unique RENAME TO card_sources_unique")
    op.execute("ALTER INDEX signal_sources_lookup_idx RENAME TO card_sources_lookup_idx")
    op.execute("ALTER INDEX signal_sources_signal_idx RENAME TO card_sources_card_idx")
    op.execute(
        "ALTER INDEX signals_triggering_message_kind_uidx "
        "RENAME TO cards_triggering_message_kind_uidx",
    )
    op.execute("ALTER INDEX signals_project_updated_idx RENAME TO cards_project_updated_idx")
    op.execute("ALTER INDEX signals_project_kind_idx RENAME TO cards_project_kind_idx")
    op.execute("ALTER INDEX signals_org_idx RENAME TO cards_org_idx")

    op.execute("ALTER TABLE digests RENAME COLUMN signal_ids TO card_ids")
    op.execute("ALTER TABLE signal_sources RENAME COLUMN signal_id TO card_id")
    op.execute("ALTER TABLE signal_sources RENAME TO card_sources")
    op.execute("ALTER TABLE signals RENAME TO cards")
