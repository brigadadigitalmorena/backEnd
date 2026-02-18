"""Notification model."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Notification(Base):
    """Admin notification model."""
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    type       = Column(String(50), nullable=False)          # survey_created, assignment_created, user_registered, version_published, survey_deleted
    title      = Column(String(255), nullable=False)
    message    = Column(Text, nullable=False)
    read       = Column(Boolean, default=False, nullable=False)
    action_url = Column(String(255), nullable=True)          # "/dashboard/surveys" etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
