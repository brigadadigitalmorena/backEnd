"""Notification model."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Notification(Base):
    """Notification model. user_id=None means global (admin-wide) notification."""
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    type       = Column(String(50), nullable=False)          # survey_created, assignment_created, user_registered, version_published, survey_deleted
    title      = Column(String(255), nullable=False)
    message    = Column(Text, nullable=False)
    read       = Column(Boolean, default=False, nullable=False)
    action_url = Column(String(255), nullable=True)          # "/dashboard/surveys" etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="notifications", foreign_keys=[user_id])
