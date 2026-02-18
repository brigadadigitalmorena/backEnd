"""Add starts_at and ends_at to surveys

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-17 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('surveys',
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('surveys',
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('surveys', 'ends_at')
    op.drop_column('surveys', 'starts_at')
