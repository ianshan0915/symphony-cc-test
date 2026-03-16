"""Add assistant_skills join table and remove temperature/max_tokens from assistants.

Revision ID: 008
Revises: 007
Create Date: 2026-03-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- Create assistant_skills join table ---
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'public' AND table_name = 'assistant_skills'"
            ")"
        )
    )
    if not result.scalar():
        op.create_table(
            "assistant_skills",
            sa.Column(
                "assistant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("assistants.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "skill_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("skills.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        )

    # --- Remove temperature and max_tokens columns from assistants ---
    # Check if columns exist before dropping (idempotent)
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'assistants' "
            "AND column_name IN ('temperature', 'max_tokens')"
        )
    )
    existing_cols = {row[0] for row in result.fetchall()}

    if "temperature" in existing_cols:
        op.drop_column("assistants", "temperature")
    if "max_tokens" in existing_cols:
        op.drop_column("assistants", "max_tokens")


def downgrade() -> None:
    # Re-add temperature and max_tokens columns
    op.add_column(
        "assistants",
        sa.Column("temperature", sa.Float(), nullable=True),
    )
    op.add_column(
        "assistants",
        sa.Column("max_tokens", sa.Integer(), nullable=True),
    )

    # Drop the join table
    op.drop_table("assistant_skills")
