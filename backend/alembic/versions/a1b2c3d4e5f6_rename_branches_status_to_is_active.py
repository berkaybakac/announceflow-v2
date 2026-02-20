"""rename branches.status to is_active

Revision ID: a1b2c3d4e5f6
Revises: cae87dca0f53
Create Date: 2026-02-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'cae87dca0f53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('branches', 'status', new_column_name='is_active')


def downgrade() -> None:
    op.alter_column('branches', 'is_active', new_column_name='status')
