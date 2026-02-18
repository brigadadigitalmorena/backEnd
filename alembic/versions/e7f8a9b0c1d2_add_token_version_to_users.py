"""add token_version to users

Revision ID: e7f8a9b0c1d2
Revises: 4d8aceb40133
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = '4d8aceb40133'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'token_version',
            sa.Integer(),
            nullable=False,
            server_default='1',
        )
    )


def downgrade() -> None:
    op.drop_column('users', 'token_version')
