"""Add created_at to schedules + conflict lookup partial index.

Revision ID: d4e5f6a7b8c9
Revises: c6b2f55d4a1e
Create Date: 2026-02-24 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c6b2f55d4a1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. created_at column ekle
    op.add_column(
        "schedules",
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 2. Çakışma sorgusu için partial B-Tree index
    op.create_index(
        "ix_schedules_conflict_lookup",
        "schedules",
        ["play_at", "end_time"],
        postgresql_where=sa.text("play_at IS NOT NULL AND is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_schedules_conflict_lookup", table_name="schedules")
    op.drop_column("schedules", "created_at")
