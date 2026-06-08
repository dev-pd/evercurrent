"""Phase 10: Drive ingest — extend documents + document_chunks for multi-tenant.

The Phase 1 `documents` table was single-tenant + body-bearing (PRD-style
docs with full body stashed in `body TEXT`). Phase 10 wires Google Drive
as a real ingest source, so documents become:

- multi-tenant (org_id, RLS policy)
- provenance-tracked (source, external_id, UNIQUE for idempotent ingest)
- ingest-timestamped (ingested_at, separate from created_at)

We keep `body` nullable for backward compatibility with Phase 1 seed data
that still relies on the full body for indexer reruns; new Drive-sourced
documents leave it NULL and rely on `document_chunks` for retrieval.

`document_chunks` already has the right shape from Phase 1; we just need
to ensure the HNSW index exists (Phase 1 only had the b-tree dedupe).

Revision ID: 0009_drive_documents
Revises: 0008_cards
Create Date: 2026-06-08 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_drive_documents"
down_revision: str | None = "0008_cards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `body` was NOT NULL in Phase 1 because every doc was a markdown
    # blob loaded from disk. Drive-sourced docs persist content only as
    # chunks, so loosen the constraint here.
    op.alter_column("documents", "body", existing_type=sa.Text, nullable=True)

    op.add_column(
        "documents",
        sa.Column("source", sa.Text, nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("external_id", sa.Text, nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Phase 1 docs predate the (source, external_id) shape — backfill
    # with synthetic values derived from the row id so the UNIQUE
    # constraint we add next stays valid.
    op.execute(
        """
        UPDATE documents
        SET source = COALESCE(source, 'seed'),
            external_id = COALESCE(external_id, id::text)
        """,
    )
    op.alter_column("documents", "source", existing_type=sa.Text, nullable=False)
    op.alter_column("documents", "external_id", existing_type=sa.Text, nullable=False)

    op.create_unique_constraint(
        "documents_source_external_id_unique",
        "documents",
        ["source", "external_id"],
    )
    op.create_index(
        "documents_source_lookup_idx",
        "documents",
        ["source", "external_id"],
    )

    # RLS: Phase 5 (0005_orgs_and_rls) already added the policy when it
    # backfilled `org_id` on `documents`; we don't need to redo it. We do
    # need to ensure the HNSW vector index exists on chunks.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS document_chunks_hnsw_idx
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        """,
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS document_chunks_hnsw_idx")
    op.drop_index("documents_source_lookup_idx", table_name="documents")
    op.drop_constraint(
        "documents_source_external_id_unique",
        "documents",
        type_="unique",
    )
    op.drop_column("documents", "ingested_at")
    op.drop_column("documents", "external_id")
    op.drop_column("documents", "source")
    op.alter_column(
        "documents",
        "body",
        existing_type=postgresql.TEXT(),
        nullable=False,
    )
