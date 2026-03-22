"""Add user_id column to assistants table for user-scoped agents.

Revision ID: 009
Revises: 008
Create Date: 2026-03-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: str = "008"
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
            "  AND table_name = 'assistants'"
            "  AND column_name = 'user_id'"
            ")"
        )
    )
    if not result.scalar():
        op.add_column(
            "assistants",
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
                index=True,
            ),
        )


def downgrade() -> None:
    op.drop_column("assistants", "user_id")
