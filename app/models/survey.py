"""Survey models."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.core.database import Base


class QuestionType(str, Enum):
    """Question types supported by the system."""
    # Text inputs
    TEXT = "text"
    TEXTAREA = "textarea"
    EMAIL = "email"
    PHONE = "phone"
    # Numeric
    NUMBER = "number"
    SLIDER = "slider"
    SCALE = "scale"
    RATING = "rating"
    # Choice
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    YES_NO = "yes_no"
    # Date/Time
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    # Media & special
    PHOTO = "photo"
    FILE = "file"
    SIGNATURE = "signature"
    LOCATION = "location"
    INE_OCR = "ine_ocr"


class Survey(Base):
    """
    Survey model - represents a survey template.
    Immutable once published (versioning via SurveyVersion).
    """
    
    __tablename__ = "surveys"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, nullable=False)  # User ID of creator
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    estimated_duration_minutes = Column(Integer, nullable=True)  # approx fill time
    max_responses = Column(Integer, nullable=True)              # response cap, None = unlimited
    allow_anonymous = Column(Boolean, default=False, nullable=False)  # allow without brigadista assignment
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Relationships
    versions = relationship("SurveyVersion", back_populates="survey", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="survey", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Survey(id={self.id}, title={self.title})>"


class SurveyVersion(Base):
    """
    Survey version model - represents an immutable version of a survey.
    Each version has its own set of questions.
    """
    
    __tablename__ = "survey_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)  # 1, 2, 3, etc.
    is_published = Column(Boolean, default=False, nullable=False)
    change_summary = Column(Text, nullable=True)  # Description of changes from previous version
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    survey = relationship("Survey", back_populates="versions")
    questions = relationship(
        "Question",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="Question.order",
    )
    responses = relationship("SurveyResponse", back_populates="version")
    
    def __repr__(self):
        return f"<SurveyVersion(id={self.id}, survey_id={self.survey_id}, version={self.version_number})>"


class Question(Base):
    """Question model - belongs to a specific survey version."""
    
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("survey_versions.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(SQLEnum(QuestionType), nullable=False)
    order = Column(Integer, nullable=False)  # Display order
    is_required = Column(Boolean, default=False, nullable=False)
    validation_rules = Column(JSON, nullable=True)  # Store min/max, regex, etc.
    
    # Relationships
    version = relationship("SurveyVersion", back_populates="questions")
    options = relationship("AnswerOption", back_populates="question", cascade="all, delete-orphan")
    answers = relationship("QuestionAnswer", back_populates="question")
    
    def __repr__(self):
        return f"<Question(id={self.id}, type={self.question_type}, text={self.question_text[:30]})>"


class AnswerOption(Base):
    """Answer options for choice-based questions."""
    
    __tablename__ = "answer_options"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    option_text = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    
    # Relationships
    question = relationship("Question", back_populates="options")
    
    def __repr__(self):
        return f"<AnswerOption(id={self.id}, text={self.option_text})>"
