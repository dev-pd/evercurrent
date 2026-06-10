"""Phase 2: orgs + org_memberships + RLS scaffolding.

Adds the multi-tenant foundation: orgs table, org_memberships table,
and a Postgres function `set_org_context(uuid)` that the application
middleware calls at the start of every request to set the session
variable RLS policies will read.

Tenant-scoped tables (projects, messages, documents, etc.) get an
`org_id` column + RLS policy in this migration too, so subsequent
phases can rely on RLS being enforced everywhere.

Revision ID: 0005_orgs_and_rls
Revises: 0004_project_start_date
Create Date: 2026-06-07 20:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_orgs_and_rls"
down_revision: str | None = "0004_project_start_date"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TENANT_TABLES: tuple[str, ...] = (
    "projects",
    "channels",
    "messages",
    "message_tags",
    "documents",
    "digests",
    "decisions",
    "users",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "orgs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("auth0_org_id", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("plan", sa.Text, nullable=False, server_default="free"),
        sa.Column("region", sa.Text, nullable=False, server_default="us-east"),
        sa.Column("itar", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "org_memberships",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("auth0_user_id", sa.Text, nullable=False),
        sa.Column("slack_user_id", sa.Text, nullable=True),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False, server_default="member"),
        sa.Column("timezone", sa.Text, nullable=False, server_default="UTC"),
        sa.Column("quiet_start", sa.Time, nullable=True),
        sa.Column("quiet_end", sa.Time, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("role IN ('admin','member')", name="org_memberships_role_check"),
        sa.UniqueConstraint("org_id", "auth0_user_id", name="org_memberships_unique"),
    )
    op.create_index(
        "org_memberships_auth0_user_idx",
        "org_memberships",
        ["auth0_user_id"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_org_context(p_org_id uuid)
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
            PERFORM set_config('app.current_org_id', p_org_id::text, true);
        END;
        $$;
        """,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION clear_org_context()
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
            PERFORM set_config('app.current_org_id', '', true);
        END;
        $$;
        """,
    )

    # Backfill: every existing tenant-scoped table gets org_id, default to a
    # synthetic legacy org so existing rows continue to be readable until
    # Phase 9 finishes the data model swap.
    bind = op.get_bind()
    legacy_org_id = bind.execute(
        sa.text(
            "INSERT INTO orgs (auth0_org_id, name) VALUES ('legacy', 'Legacy Org')"
            " RETURNING id",
        ),
    ).scalar_one()

    for table in TENANT_TABLES:
        # Schema may differ between tables; skip those that don't yet exist.
        exists = bind.execute(
            sa.text("SELECT to_regclass(:t)"),
            {"t": table},
        ).scalar_one()
        if not exists:
            continue
        op.add_column(
            table,
            sa.Column(
                "org_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.execute(  # noqa: S608
            sa.text(f"UPDATE {table} SET org_id = :id").bindparams(id=legacy_org_id),
        )
        op.alter_column(table, "org_id", nullable=False)
        op.create_foreign_key(
            f"{table}_org_id_fkey",
            table,
            "orgs",
            ["org_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"{table}_org_idx", table, ["org_id"])
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


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.drop_index(f"{table}_org_idx", table_name=table, if_exists=True)
        op.drop_constraint(f"{table}_org_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "org_id")

    op.execute("DROP FUNCTION IF EXISTS clear_org_context()")
    op.execute("DROP FUNCTION IF EXISTS set_org_context(uuid)")
    op.drop_index("org_memberships_auth0_user_idx", table_name="org_memberships")
    op.drop_table("org_memberships")
    op.drop_table("orgs")
