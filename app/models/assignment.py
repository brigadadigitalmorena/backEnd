"""Assignment models."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.core.database import Base


class AssignmentStatus(str, Enum):
    """Assignment status — whether the user is currently authorized to fill the survey."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Assignment(Base):
    """
    Assignment model - links a user (brigadista or encargado) to a survey.

    Flow:
      Admin / Encargado  →  creates Assignment (status: active)  →  user can fill the survey N times
      Admin / Encargado  →  sets status: inactive  →  user loses access
      Responses are tracked separately in survey_responses table (N per assignment)
    """

    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    # The user who must fill the survey (brigadista OR encargado)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    # FK to the user who created this assignment (admin / encargado)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(
        SQLEnum(AssignmentStatus, values_callable=lambda x: [e.value for e in x]),
        default=AssignmentStatus.ACTIVE,
        nullable=False,
    )
    location = Column(String, nullable=True)   # Optional: area/zone/colonia
    notes = Column(Text, nullable=True)         # Instructions from the encargado
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="assignments")
    assigned_by_user = relationship("User", foreign_keys=[assigned_by])
    survey = relationship("Survey", back_populates="assignments")

    def __repr__(self):
        return f"<Assignment(id={self.id}, user_id={self.user_id}, survey_id={self.survey_id}, status={self.status})>"
