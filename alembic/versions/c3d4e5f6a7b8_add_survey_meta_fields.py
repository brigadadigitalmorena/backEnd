"""Add estimated_duration_minutes, max_responses, allow_anonymous to surveys

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-17 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('surveys',
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True))
    op.add_column('surveys',
        sa.Column('max_responses', sa.Integer(), nullable=True))
    op.add_column('surveys',
        sa.Column('allow_anonymous', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('surveys', 'allow_anonymous')
    op.drop_column('surveys', 'max_responses')
    op.drop_column('surveys', 'estimated_duration_minutes')
