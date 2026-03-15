"""Add skills table for user-created agent skills.

Revision ID: 007
Revises: 006
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Guard for environments where create_all() already created the table.
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'public' AND table_name = 'skills'"
            ")"
        )
    )
    if result.scalar():
        return

    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(1024), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Index on user_id for filtering user's own skills
    op.create_index("ix_skills_user_id", "skills", ["user_id"])
    # Unique constraint: skill name per user (NULL user_id = system-wide)
    op.create_index(
        "ix_skills_user_name",
        "skills",
        ["user_id", "name"],
        unique=True,
    )
    # Index on is_active for filtering
    op.create_index("ix_skills_is_active", "skills", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_skills_is_active", table_name="skills")
    op.drop_index("ix_skills_user_name", table_name="skills")
    op.drop_index("ix_skills_user_id", table_name="skills")
    op.drop_table("skills")
