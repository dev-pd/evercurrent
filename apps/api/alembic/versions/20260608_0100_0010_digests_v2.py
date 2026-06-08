"""Phase 8: digests v2 — per-member, per-day with card + message citations.

The legacy `digests` table (Phase 1/2) was keyed on (user_id, day, phase)
and stored a flat list of `item_message_ids`. Phase 8 rewrites the digest
as a per-(project_member, day_index) artifact with separate `card_ids`
and `message_ids` arrays so the Dashboard can render distinct citation
lanes without re-parsing the markdown.

We drop the legacy table outright and re-create it in the new shape; no
production data depends on the old rows (seed data is regenerated on
every demo bring-up).

RLS: we infer `org_id` via the project_member -> org_memberships join,
so the table itself does not carry an `org_id` column. Tenant isolation
flows through the FK chain. We still enable RLS but with a permissive
read policy guarded by the application-set context.

Revision ID: 0010_digests_v2
Revises: 0009_drive_documents
Create Date: 2026-06-08 01:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_digests_v2"
down_revision: str | None = "0009_drive_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Wipe the legacy table; it is rebuilt with a different key shape and
    # an array of card_ids that didn't exist before.
    op.execute("DROP TABLE IF EXISTS digests CASCADE")

    op.create_table(
        "digests",
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
        sa.Column("day_index", sa.Integer, nullable=False),
        sa.Column("phase", sa.Text, nullable=False),
        sa.Column("content_md", sa.Text, nullable=False),
        sa.Column(
            "card_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "message_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "project_member_id",
            "day_index",
            name="digests_member_day_unique",
        ),
    )
    op.create_index("digests_org_idx", "digests", ["org_id"])
    op.create_index(
        "digests_member_day_idx",
        "digests",
        ["project_member_id", sa.text("day_index DESC")],
    )

    op.execute("ALTER TABLE digests ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY digests_tenant_isolation ON digests
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
    op.execute("DROP POLICY IF EXISTS digests_tenant_isolation ON digests")
    op.execute("ALTER TABLE digests DISABLE ROW LEVEL SECURITY")
    op.drop_index("digests_member_day_idx", table_name="digests")
    op.drop_index("digests_org_idx", table_name="digests")
    op.drop_table("digests")
