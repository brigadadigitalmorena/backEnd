"""Survey schemas."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.survey import QuestionType


# Answer option schemas
class AnswerOptionBase(BaseModel):
    """Base answer option schema."""
    option_text: str
    order: int


class AnswerOptionCreate(AnswerOptionBase):
    """Create answer option."""
    pass


class AnswerOptionResponse(AnswerOptionBase):
    """Answer option response."""
    id: int
    
    model_config = ConfigDict(from_attributes=True)


# Question schemas
class QuestionBase(BaseModel):
    """Base question schema."""
    question_text: str
    question_type: QuestionType
    order: int
    is_required: bool = False
    validation_rules: Optional[Dict[str, Any]] = None


class QuestionCreate(QuestionBase):
    """Create question with options."""
    options: Optional[List[AnswerOptionCreate]] = None


class QuestionResponse(QuestionBase):
    """Question response."""
    id: int
    version_id: int
    options: List[AnswerOptionResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


# Survey version schemas
class SurveyVersionResponse(BaseModel):
    """Survey version response."""
    id: int
    version_number: int
    is_published: bool
    change_summary: Optional[str] = None
    created_at: datetime
    questions: List[QuestionResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


# Survey schemas
class SurveyBase(BaseModel):
    """Base survey schema."""
    title: str
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    max_responses: Optional[int] = None
    allow_anonymous: bool = False


class SurveyCreate(SurveyBase):
    """Create survey with questions."""
    questions: List[QuestionCreate] = Field(..., min_length=1)


class SurveyUpdate(BaseModel):
    """Update survey (creates new version)."""
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    max_responses: Optional[int] = None
    allow_anonymous: Optional[bool] = None
    questions: Optional[List[QuestionCreate]] = None
    change_summary: Optional[str] = None


class SurveyResponse(SurveyBase):
    """Survey response."""
    id: int
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    versions: List[SurveyVersionResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class SurveyListResponse(SurveyBase):
    """Survey list response (without versions)."""
    id: int
    is_active: bool
    created_by: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AssignedSurveyResponse(BaseModel):
    """Assigned survey response for mobile app."""
    assignment_id: int
    survey_id: int
    survey_title: str
    survey_description: Optional[str] = None
    assignment_status: str
    assigned_location: Optional[str] = None
    latest_version: SurveyVersionResponse
    assigned_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
