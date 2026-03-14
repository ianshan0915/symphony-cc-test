"""Add checkpoints table for LangGraph state persistence.

Revision ID: 002
Revises: 001
Create Date: 2026-03-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checkpoints",
        sa.Column("thread_id", sa.Text(), primary_key=True),
        sa.Column("checkpoint_ns", sa.Text(), primary_key=True, server_default=""),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        sa.Column("parent_checkpoint_id", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("checkpoint", postgresql.JSONB(), nullable=False),
        sa.Column("metadata_", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "checkpoint_writes",
        sa.Column("thread_id", sa.Text(), primary_key=True),
        sa.Column("checkpoint_ns", sa.Text(), primary_key=True, server_default=""),
        sa.Column("checkpoint_id", sa.Text(), primary_key=True),
        sa.Column("task_id", sa.Text(), primary_key=True),
        sa.Column("idx", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("blob", sa.LargeBinary(), nullable=False),
    )

    op.create_table(
        "checkpoint_blobs",
        sa.Column("thread_id", sa.Text(), primary_key=True),
        sa.Column("checkpoint_ns", sa.Text(), primary_key=True, server_default=""),
        sa.Column("channel", sa.Text(), primary_key=True),
        sa.Column("version", sa.Text(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("blob", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("checkpoint_blobs")
    op.drop_table("checkpoint_writes")
    op.drop_table("checkpoints")
