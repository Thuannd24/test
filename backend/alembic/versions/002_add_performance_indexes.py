"""Add performance indexes for todos and users tables.

Revision ID: 002_add_performance_indexes
Revises: a0790c76a129
Create Date: 2026-09-16

Context (Tier 3C):
    After seeding 1,000,000 todos across 10,000 users and running EXPLAIN ANALYZE,
    the core queries showed sequential scans (Seq Scan) on the todos table.

    Core queries analyzed:
    1. SELECT * FROM todos WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2;
       → Was: Seq Scan + Sort (very slow with 1M rows)
       → After: Index Scan on idx_todos_user_created_at

    2. SELECT * FROM todos WHERE user_id = $1 AND completed = $2 ORDER BY created_at DESC;
       → After: Index Only Scan on idx_todos_user_completed_created (composite covers all 3 columns)

    3. SELECT * FROM users WHERE email = $1;
       → Was: Seq Scan (no index on email column, and missing UNIQUE constraint)
       → After: Index Scan on idx_users_email (unique)

    See docs/DB_BENCHMARK.md for full EXPLAIN ANALYZE output and timing comparison.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_add_performance_indexes"
down_revision: Union[str, None] = "a0790c76a129"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── todos: individual user_id index ────────────────────────────────────
    # Used by: all todo list queries WHERE user_id = $1
    op.create_index(
        "idx_todos_user_id",
        "todos",
        ["user_id"],
        unique=False,
    )

    # ── todos: composite index for filtered + ordered queries ────────────────
    # Used by: WHERE user_id=$1 AND completed=$2 ORDER BY created_at DESC
    # Column order follows the selectivity rule: user_id (high selectivity) first,
    # then completed (boolean, low selectivity), then created_at (for sort).
    # PostgreSQL can also use this index for queries that only filter on user_id.
    op.create_index(
        "idx_todos_user_completed_created",
        "todos",
        ["user_id", "completed", sa.text("created_at DESC")],
        unique=False,
    )

    # ── users: unique email index ────────────────────────────────────────────
    # Used by: login lookup (WHERE email = $1)
    # Also adds the MISSING unique constraint that was absent from the initial
    # migration – without it, duplicate emails could be inserted at DB level.
    op.create_index(
        "idx_users_email",
        "users",
        ["email"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_users_email", table_name="users")
    op.drop_index("idx_todos_user_completed_created", table_name="todos")
    op.drop_index("idx_todos_user_id", table_name="todos")
