"""orgs.llm_enabled: per-org opt-in for paid AI features

Revision ID: c4e1a9d27b30
Revises: 81fb72ee86e3
Create Date: 2026-11-23

Existing orgs start disabled (server default false); the operator enables the ones that should
keep AI features with `rh llm-access <org-id>`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e1a9d27b30"
down_revision: str | Sequence[str] | None = "81fb72ee86e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("llm_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("orgs", "llm_enabled")
