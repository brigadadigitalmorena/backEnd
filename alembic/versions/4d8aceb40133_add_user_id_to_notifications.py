"""add_user_id_to_notifications

Revision ID: 4d8aceb40133
Revises: bcd0269350da
Create Date: 2026-02-18 11:13:48.624842

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4d8aceb40133'
down_revision = 'bcd0269350da'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('notifications', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_notifications_user_id', 'notifications', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_constraint('fk_notifications_user_id', 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'user_id')
