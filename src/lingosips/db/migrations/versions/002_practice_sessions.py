"""002_practice_sessions

Revision ID: a1b2c3d4e5f6
Revises: e328b921ead2
Create Date: 2026-05-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "e328b921ead2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add practice_sessions table and session_id column to reviews."""
    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "reviews",
        sa.Column("session_id", sa.Integer(), nullable=True),
    )
    # Note: SQLite does not support ALTER TABLE ADD CONSTRAINT, so the FK relationship
    # is enforced at the SQLModel layer only. The index is created for query performance.
    op.create_index("ix_reviews_session_id", "reviews", ["session_id"], unique=False)


def downgrade() -> None:
    """Remove practice_sessions table and session_id column from reviews."""
    op.drop_index("ix_reviews_session_id", table_name="reviews")
    op.drop_column("reviews", "session_id")
    op.drop_table("practice_sessions")
