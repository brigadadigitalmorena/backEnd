"""User model."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.core.database import Base


class UserRole(str, Enum):
    """User roles in the system."""
    ADMIN = "admin"
    ENCARGADO = "encargado"
    BRIGADISTA = "brigadista"


class User(Base):
    """User model."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.BRIGADISTA)
    is_active = Column(Boolean, default=True, nullable=False)
    token_version = Column(Integer, default=1, nullable=False, server_default="1")  # Incremented on logout/refresh to invalidate old tokens
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    assignments = relationship("Assignment", foreign_keys="Assignment.user_id", back_populates="user", cascade="all, delete-orphan")
    survey_responses = relationship("SurveyResponse", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    
    # Activation system relationships
    supervised_whitelist = relationship("UserWhitelist", foreign_keys="UserWhitelist.assigned_supervisor_id", back_populates="assigned_supervisor")
    whitelist_activation = relationship("UserWhitelist", foreign_keys="UserWhitelist.activated_user_id", back_populates="activated_user")
    created_whitelist = relationship("UserWhitelist", foreign_keys="UserWhitelist.created_by", back_populates="creator")
    used_activation_codes = relationship("ActivationCode", foreign_keys="ActivationCode.used_by_user_id", back_populates="used_by_user")
    generated_activation_codes = relationship("ActivationCode", foreign_keys="ActivationCode.generated_by", back_populates="generator")
    activation_audit_logs = relationship("ActivationAuditLog", foreign_keys="ActivationAuditLog.created_user_id", back_populates="created_user")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
