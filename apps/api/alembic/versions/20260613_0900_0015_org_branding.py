"""Phase 16: per-org branding (white-label).

Each tenant gets a small branding blob (accent color + monogram) the API
returns so the frontend themes itself per company without any hardcoded
company info. Seeds the two demo orgs with distinct names + colors.

Revision ID: 0015_org_branding
Revises: 0014_rls_hardening
Create Date: 2026-06-13 09:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_org_branding"
down_revision = "0014_rls_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orgs",
        sa.Column(
            "branding",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.execute(
        """
        UPDATE orgs SET name = 'Helix Robotics',
          branding = '{"accent": "#4f46e5", "monogram": "H"}'
        WHERE auth0_org_id = 'legacy'
        """,
    )
    op.execute(
        """
        UPDATE orgs SET name = 'Acme Drones',
          branding = '{"accent": "#0891b2", "monogram": "A"}'
        WHERE auth0_org_id = 'orgB'
        """,
    )


def downgrade() -> None:
    op.drop_column("orgs", "branding")
