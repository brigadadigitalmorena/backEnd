"""Assignment schemas."""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

from app.models.assignment import AssignmentStatus


class AssignmentBase(BaseModel):
    """Base assignment schema."""
    location: Optional[str] = None


class AssignmentCreate(AssignmentBase):
    """Create assignment."""
    user_id: int
    survey_id: int


class AssignmentUpdate(BaseModel):
    """Update assignment."""
    status: Optional[AssignmentStatus] = None
    location: Optional[str] = None


class AssignmentResponse(AssignmentBase):
    """Assignment response."""
    id: int
    user_id: int
    survey_id: int
    assigned_by: int
    status: AssignmentStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class UserMini(BaseModel):
    """Minimal user info for assignment detail."""
    id: int
    full_name: str
    email: str
    model_config = ConfigDict(from_attributes=True)


class SurveyMini(BaseModel):
    """Minimal survey info for assignment detail."""
    id: int
    title: str
    model_config = ConfigDict(from_attributes=True)


class AssignmentDetailResponse(BaseModel):
    """Assignment with embedded user and survey names (admin list view)."""
    id: int
    user_id: int
    user: UserMini
    survey_id: int
    survey: SurveyMini
    assigned_by: int
    status: AssignmentStatus
    location: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
