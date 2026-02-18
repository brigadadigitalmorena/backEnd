"""Add admin_audit_log table, users.deleted_at, and performance indexes

Revision ID: c5d6e7f8a9b0
Revises: f3c1b8a2d9e1
Create Date: 2026-02-18 10:00:00.000000

Changes:
    1. users.deleted_at  — soft-delete timestamp (NULL = live account)
    2. admin_audit_log   — append-only audit trail for destructive admin actions
    3. Composite indexes for hot query paths:
         users(role, is_active)
         survey_responses(version_id, completed_at)
         survey_responses(user_id, completed_at)
         question_answers(response_id, question_id)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c5d6e7f8a9b0"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. users.deleted_at ──────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])

    # ── 2. admin_audit_log table ─────────────────────────────────────────────
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("action", sa.String(80), nullable=False, index=True),
        sa.Column("target_type", sa.String(40), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True, index=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            index=True,
        ),
    )

    # ── 3. Performance indexes ────────────────────────────────────────────────
    # users: admins often filter by role + active status simultaneously
    op.create_index(
        "ix_users_role_is_active",
        "users",
        ["role", "is_active"],
    )

    # survey_responses: summary & timeline queries join+filter on version_id then order by completed_at
    op.create_index(
        "ix_survey_responses_version_completed",
        "survey_responses",
        ["version_id", "completed_at"],
    )

    # survey_responses: per-user response lookups and counts
    op.create_index(
        "ix_survey_responses_user_completed",
        "survey_responses",
        ["user_id", "completed_at"],
    )

    # question_answers: export query filters by response_id and orders/groups by question_id
    op.create_index(
        "ix_question_answers_response_question",
        "question_answers",
        ["response_id", "question_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_question_answers_response_question", table_name="question_answers")
    op.drop_index("ix_survey_responses_user_completed", table_name="survey_responses")
    op.drop_index("ix_survey_responses_version_completed", table_name="survey_responses")
    op.drop_index("ix_users_role_is_active", table_name="users")
    op.drop_table("admin_audit_log")
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "deleted_at")
