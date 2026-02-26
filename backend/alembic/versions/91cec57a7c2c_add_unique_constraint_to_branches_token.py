"""add unique constraint to branches token

Revision ID: 91cec57a7c2c
Revises: d4e5f6a7b8c9
Create Date: 2026-02-26 16:44:44.031864

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '91cec57a7c2c'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_branches_token",
        "branches",
        ["token"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_branches_token",
        "branches",
        type_="unique",
    )
