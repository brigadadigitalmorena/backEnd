"""Activation Audit Log Model"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, BigInteger, Integer, String, Boolean, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class ActivationAuditLog(Base):
    """
    Security audit trail for all activation-related events.
    Provides comprehensive logging for security monitoring and debugging.
    """
    __tablename__ = "activation_audit_log"

    # Primary Key
    id = Column(BigInteger, primary_key=True, index=True)

    # Event information
    event_type = Column(String(50), nullable=False)
    activation_code_id = Column(Integer, ForeignKey("activation_codes.id", ondelete="SET NULL"), nullable=True)
    whitelist_id = Column(Integer, ForeignKey("user_whitelist.id", ondelete="SET NULL"), nullable=True)

    # Request details
    identifier_attempted = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=False, index=True)
    user_agent = Column(Text, nullable=True)
    device_id = Column(String(255), nullable=True)

    # Result
    success = Column(Boolean, nullable=False, index=True)
    failure_reason = Column(String(255), nullable=True)

    # User created (if successful activation)
    created_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Additional context
    request_metadata = Column(JSONB, nullable=True)  # Store additional context as JSON

    # Timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    # Relationships
    activation_code = relationship("ActivationCode", back_populates="audit_logs")
    whitelist_entry = relationship("UserWhitelist", back_populates="audit_logs")
    created_user = relationship("User", foreign_keys=[created_user_id], back_populates="activation_audit_logs")

    # Constraints
    __table_args__ = (
        CheckConstraint(
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
            name="check_event_type"
        ),
    )

    def __repr__(self) -> str:
        return f"<ActivationAuditLog(id={self.id}, event={self.event_type}, success={self.success}, ip={self.ip_address})>"
