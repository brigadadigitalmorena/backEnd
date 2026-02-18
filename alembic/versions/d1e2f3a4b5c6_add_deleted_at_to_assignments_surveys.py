"""Add deleted_at to assignments and surveys (soft delete)

Revision ID: d1e2f3a4b5c6
Revises: c5d6e7f8a9b0
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # assignments.deleted_at
    op.add_column(
        "assignments",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_assignments_deleted_at",
        "assignments",
        ["deleted_at"],
    )

    # surveys.deleted_at
    op.add_column(
        "surveys",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_surveys_deleted_at",
        "surveys",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_surveys_deleted_at", table_name="surveys")
    op.drop_column("surveys", "deleted_at")

    op.drop_index("ix_assignments_deleted_at", table_name="assignments")
    op.drop_column("assignments", "deleted_at")
