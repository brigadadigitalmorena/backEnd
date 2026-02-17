"""Update activation audit event types

Revision ID: f3c1b8a2d9e1
Revises: d56fad6cd7db
Create Date: 2026-02-17 12:15:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "f3c1b8a2d9e1"
down_revision = "d56fad6cd7db"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("check_event_type", "activation_audit_log", type_="check")
    op.create_check_constraint(
        "check_event_type",
        "activation_audit_log",
        """
            event_type IN (
                'code_generated',
                'code_extended',
                'code_validation_attempt',
                'code_validation_success',
                'activation_attempt',
                'activation_success',
                'activation_failed',
                'code_expired',
                'code_locked',
                'code_revoked',
                'email_sent',
                'email_resent',
                'rate_limit_exceeded'
            )
        """,
    )


def downgrade() -> None:
    op.drop_constraint("check_event_type", "activation_audit_log", type_="check")
    op.create_check_constraint(
        "check_event_type",
        "activation_audit_log",
        """
            event_type IN (
                'code_generated',
                'code_validation_attempt',
                'code_validation_success',
                'activation_attempt',
                'activation_success',
                'activation_failed',
                'code_expired',
                'code_locked',
                'code_revoked',
                'rate_limit_exceeded'
            )
        """,
    )
