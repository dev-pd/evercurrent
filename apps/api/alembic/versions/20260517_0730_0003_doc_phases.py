"""documents.phases for phase-aware retrieval

Adds a `phases TEXT[]` column listing the project phases a document is
authoritative for. PRD is typically all phases; a test report is bound to
the phase it was run under; an ECO log is multi-phase.

The seeder populates this from a constant map keyed by document kind.

Revision ID: 0003_doc_phases
Revises: 0002_digests_per_phase
Create Date: 2026-05-17 07:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_doc_phases"
down_revision: str | None = "0002_digests_per_phase"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "phases",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index(
        "ix_documents_phases_gin",
        "documents",
        ["phases"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_documents_phases_gin", table_name="documents")
    op.drop_column("documents", "phases")
