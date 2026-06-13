"""Phase 15: real tenant isolation.

The app previously connected as the DB superuser/owner, which bypasses RLS
entirely, and the policies were fail-open (access granted when no org context
is set). This migration:

- creates a non-superuser `app_rw` role the app connects as (RLS applies to
  non-owners automatically; migrations keep running as the owner, which
  bypasses RLS as intended)
- rewrites every tenant policy fail-closed (deny when no/empty org context)
- enables RLS on the tables that were missing it (org_memberships, insights,
  orgs, document_chunks)

Revision ID: 0014_rls_hardening
Revises: 0013_insights
Create Date: 2026-06-13 08:00:00
"""

from __future__ import annotations

from alembic import op

revision = "0014_rls_hardening"
down_revision = "0013_insights"
branch_labels = None
depends_on = None

_ORG_TABLES = (
    "messages",
    "message_tags",
    "cards",
    "card_sources",
    "scores",
    "digests",
    "subscriptions",
    "notifications",
    "connectors",
    "connector_channels",
    "raw_events",
    "documents",
    "projects",
    "channels",
    "org_memberships",
    "insights",
)

_APP_ROLE = "app_rw"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
            CREATE ROLE {_APP_ROLE} LOGIN PASSWORD '{_APP_ROLE}'
              NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
          END IF;
        END $$;
        """,
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {_APP_ROLE}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {_APP_ROLE}",
    )
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_APP_ROLE}")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {_APP_ROLE}",
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {_APP_ROLE}",
    )
    op.execute(f"GRANT EXECUTE ON FUNCTION set_org_context(uuid) TO {_APP_ROLE}")
    op.execute(f"GRANT EXECUTE ON FUNCTION clear_org_context() TO {_APP_ROLE}")

    for table in _ORG_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
              USING (org_id::text = current_setting('app.current_org_id', true))
              WITH CHECK (org_id::text = current_setting('app.current_org_id', true))
            """,
        )

    op.execute("ALTER TABLE orgs ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS orgs_self ON orgs")
    op.execute(
        """
        CREATE POLICY orgs_self ON orgs
          USING (id::text = current_setting('app.current_org_id', true))
          WITH CHECK (id::text = current_setting('app.current_org_id', true))
        """,
    )

    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS document_chunks_tenant_isolation ON document_chunks")
    op.execute(
        """
        CREATE POLICY document_chunks_tenant_isolation ON document_chunks
          USING (EXISTS (
            SELECT 1 FROM documents d
            WHERE d.id = document_chunks.document_id
              AND d.org_id::text = current_setting('app.current_org_id', true)
          ))
        """,
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS document_chunks_tenant_isolation ON document_chunks")
    op.execute("ALTER TABLE document_chunks DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS orgs_self ON orgs")
    op.execute("ALTER TABLE orgs DISABLE ROW LEVEL SECURITY")
    for table in _ORG_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
              USING (
                org_id::text = COALESCE(current_setting('app.current_org_id', true), '')
                OR COALESCE(current_setting('app.current_org_id', true), '') = ''
              )
            """,
        )
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {_APP_ROLE}")
