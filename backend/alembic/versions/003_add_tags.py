"""Add tags table and todo_tags junction table for Tier 4 feature.

Revision ID: 003_add_tags
Revises: 002_add_performance_indexes
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_add_tags"
down_revision: Union[str, None] = "002_add_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tags table ───────────────────────────────────────────────────────────
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # Case-insensitive unique tag names per user
    op.execute(
        """
        CREATE UNIQUE INDEX idx_tags_user_name_ci
        ON tags (user_id, lower(name))
        """
    )

    # Index for fast tag lookup by user
    op.create_index("idx_tags_user_id", "tags", ["user_id"])

    # ── todo_tags junction table ─────────────────────────────────────────────
    op.create_table(
        "todo_tags",
        sa.Column("todo_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("todo_id", "tag_id"),
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
    )

    # Indexes for fast lookup in both directions
    op.create_index("idx_todo_tags_todo_id", "todo_tags", ["todo_id"])
    op.create_index("idx_todo_tags_tag_id", "todo_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_index("idx_todo_tags_tag_id", table_name="todo_tags")
    op.drop_index("idx_todo_tags_todo_id", table_name="todo_tags")
    op.drop_table("todo_tags")

    op.drop_index("idx_tags_user_id", table_name="tags")
    op.execute("DROP INDEX IF EXISTS idx_tags_user_name_ci")
    op.drop_table("tags")
