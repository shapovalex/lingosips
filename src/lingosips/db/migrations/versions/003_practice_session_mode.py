"""003_practice_session_mode

Revision ID: c3d4e5f6a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

revision: str = "c3d4e5f6a1b2"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add mode column to practice_sessions for active/passive recall tracking."""
    op.add_column(
        "practice_sessions",
        sa.Column("mode", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Remove mode column from practice_sessions."""
    op.drop_column("practice_sessions", "mode")
