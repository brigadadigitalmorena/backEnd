"""Activation Code Model"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ActivationCode(Base):
    """
    Time-limited activation codes for user registration.
    SECURITY: Codes are ALWAYS stored as bcrypt hashes, never in plain text.
    """
    __tablename__ = "activation_codes"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Code (ALWAYS STORED AS BCRYPT HASH, NEVER PLAIN TEXT)
    code_hash = Column(String(60), nullable=False, index=True)  # bcrypt hash is 60 chars

    # Relationships
    whitelist_id = Column(Integer, ForeignKey("user_whitelist.id", ondelete="CASCADE"), nullable=False, index=True)

    # Expiration and usage
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_used = Column(Boolean, nullable=False, default=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    used_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Security tracking
    activation_attempts = Column(Integer, nullable=False, default=0, index=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_attempt_ip = Column(String(45), nullable=True)

    # Generation metadata
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    whitelist_entry = relationship("UserWhitelist", back_populates="activation_codes")
    used_by_user = relationship("User", foreign_keys=[used_by_user_id], back_populates="used_activation_codes")
    generator = relationship("User", foreign_keys=[generated_by], back_populates="generated_activation_codes")
    audit_logs = relationship("ActivationAuditLog", back_populates="activation_code")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            """
            (is_used = TRUE AND used_at IS NOT NULL AND used_by_user_id IS NOT NULL)
            OR (is_used = FALSE AND used_at IS NULL AND used_by_user_id IS NULL)
            """,
            name="check_used_consistency"
        ),
        CheckConstraint(
            "expires_at > generated_at",
            name="check_expires_future"
        ),
        CheckConstraint(
            "activation_attempts >= 0",
            name="check_attempts_positive"
        ),
    )

    @property
    def is_expired(self) -> bool:
        """Check if code is expired"""
        return datetime.now(self.expires_at.tzinfo) > self.expires_at

    @property
    def is_locked(self) -> bool:
        """Check if code is locked (too many failed attempts)"""
        return 5 <= self.activation_attempts < 999

    @property
    def status(self) -> str:
        """Get computed status of the code"""
        if self.activation_attempts >= 999:
            return "revoked"
        if self.is_used:
            return "used"
        if self.is_locked:
            return "locked"
        if self.is_expired:
            return "expired"
        return "active"

    def __repr__(self) -> str:
        return f"<ActivationCode(id={self.id}, whitelist_id={self.whitelist_id}, status={self.status})>"
