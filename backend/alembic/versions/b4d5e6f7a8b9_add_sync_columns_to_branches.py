"""add_sync_columns_to_branches

Revision ID: b4d5e6f7a8b9
Revises: 37f6c5eaf145
Create Date: 2026-02-24 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = '37f6c5eaf145'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('branches', sa.Column('last_sync_at', sa.DateTime(), nullable=True))
    op.add_column('branches', sa.Column('sync_status', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('branches', 'sync_status')
    op.drop_column('branches', 'last_sync_at')
