"""Add user_id column to threads table for tenant isolation.

Revision ID: 010
Revises: 009
Create Date: 2026-03-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: str = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if column already exists (idempotent)
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.columns"
            "  WHERE table_schema = 'public'"
            "  AND table_name = 'threads'"
            "  AND column_name = 'user_id'"
            ")"
        )
    )
    if not result.scalar():
        op.add_column(
            "threads",
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
                index=True,
            ),
        )

    # Backfill: assign existing threads to the first user if one exists,
    # or leave NULL for manual assignment.
    op.execute(
        sa.text(
            "UPDATE threads SET user_id = ("
            "  SELECT id FROM users ORDER BY created_at ASC LIMIT 1"
            ") WHERE user_id IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("threads", "user_id")
