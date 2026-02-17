"""Add new question types to QuestionType enum

Revision ID: a1b2c3d4e5f6
Revises: 5acd0fab379c
Create Date: 2026-02-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f3c1b8a2d9e1'
branch_labels = None
depends_on = None


NEW_VALUES = [
    'textarea',
    'email',
    'phone',
    'slider',
    'scale',
    'rating',
    'yes_no',
    'time',
    'datetime',
    'file',
    'ine_ocr',
]


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE IF NOT EXISTS is safe in PostgreSQL 12+
    # It cannot run inside a transaction when the type was just created,
    # but for existing types it works fine in a regular transaction.
    for value in NEW_VALUES:
        op.execute(
            sa.text(f"ALTER TYPE questiontype ADD VALUE IF NOT EXISTS '{value}'")
        )


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum natively.
    # To rollback you would need to recreate the enum and update the column.
    # For safety, this downgrade is a no-op — the extra values won't cause issues
    # if you roll back the application code.
    pass
