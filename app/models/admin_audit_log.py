"""Admin audit log model — records destructive or sensitive admin actions."""
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class AdminAuditLog(Base):
    """
    Append-only audit trail for admin actions that create, modify, or remove
    data in a way that cannot be trivially reversed.

    Covered actions:
        user.delete          – soft-deletion of a user account
        user.role_change     – role promoted or demoted by an admin
        user.status_change   – is_active toggled by an admin
        assignment.delete    – assignment hard-deleted
    """

    __tablename__ = "admin_audit_log"

    id = Column(BigInteger, primary_key=True, index=True)

    # Who performed the action (NULL if the actor was later deleted)
    actor_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # What happened — short dot-separated noun.verb key
    action = Column(String(80), nullable=False, index=True)

    # What was affected
    target_type = Column(String(40), nullable=True)   # "user" | "assignment"
    target_id = Column(Integer, nullable=True, index=True)

    # Snapshot of relevant fields before/after the change
    # e.g. {"before": {"role": "brigadista"}, "after": {"role": "encargado"}}
    # e.g. {"email": "...", "full_name": "...", "role": "..."}
    details = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    actor = relationship(
        "User",
        foreign_keys=[actor_id],
        back_populates="admin_audit_logs",
    )

    def __repr__(self) -> str:
        return (
            f"<AdminAuditLog(id={self.id}, actor={self.actor_id}, "
            f"action={self.action}, target={self.target_type}:{self.target_id})>"
        )
