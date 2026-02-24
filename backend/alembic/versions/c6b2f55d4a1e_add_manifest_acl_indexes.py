"""add_manifest_acl_indexes

Revision ID: c6b2f55d4a1e
Revises: b4d5e6f7a8b9
Create Date: 2026-02-24 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6b2f55d4a1e"
down_revision: Union[str, Sequence[str], None] = "b4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_media_targets_target_type_target_id",
        "media_targets",
        ["target_type", "target_id"],
        unique=False,
    )
    op.create_index(
        "ix_media_targets_target_type_target_group",
        "media_targets",
        ["target_type", "target_group"],
        unique=False,
    )
    op.create_index(
        "ix_media_targets_media_id",
        "media_targets",
        ["media_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedules_is_active_target_type_target_id",
        "schedules",
        ["is_active", "target_type", "target_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedules_is_active_target_type_target_group",
        "schedules",
        ["is_active", "target_type", "target_group"],
        unique=False,
    )
    op.create_index(
        "ix_schedules_media_id",
        "schedules",
        ["media_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schedules_media_id",
        table_name="schedules",
    )
    op.drop_index(
        "ix_schedules_is_active_target_type_target_group",
        table_name="schedules",
    )
    op.drop_index(
        "ix_schedules_is_active_target_type_target_id",
        table_name="schedules",
    )
    op.drop_index(
        "ix_media_targets_media_id",
        table_name="media_targets",
    )
    op.drop_index(
        "ix_media_targets_target_type_target_group",
        table_name="media_targets",
    )
    op.drop_index(
        "ix_media_targets_target_type_target_id",
        table_name="media_targets",
    )
