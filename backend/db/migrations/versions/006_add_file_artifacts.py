"""Add file_artifacts table for agent file tools.

Revision ID: 006
Revises: 005
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Guard for environments where create_all() already created the table.
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'public' AND table_name = 'file_artifacts'"
            ")"
        )
    )
    if result.scalar():
        return

    op.create_table(
        "file_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("mime_type", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
    op.create_index("ix_file_artifacts_thread_id", "file_artifacts", ["thread_id"])
    op.create_index(
        "ix_file_artifacts_thread_path",
        "file_artifacts",
        ["thread_id", "file_path"],
    )


def downgrade() -> None:
    op.drop_index("ix_file_artifacts_thread_path", table_name="file_artifacts")
    op.drop_index("ix_file_artifacts_thread_id", table_name="file_artifacts")
    op.drop_table("file_artifacts")
