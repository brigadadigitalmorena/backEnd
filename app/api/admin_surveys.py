"""Survey router (Admin control plane)."""
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.survey_service import SurveyService
from app.schemas.survey import SurveyCreate, SurveyUpdate, SurveyResponse
from app.api.dependencies import AdminUser

router = APIRouter(prefix="/admin/surveys", tags=["Admin - Surveys"])


@router.post("", response_model=SurveyResponse, status_code=201)
def create_survey(
    survey_data: SurveyCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Create a new survey with questions (Admin only).
    
    Creates survey with initial version.
    """
    service = SurveyService(db)
    return service.create_survey(survey_data, current_user.id)


@router.get("", response_model=List[SurveyResponse])
def list_surveys(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = None
):
    """
    List all surveys (Admin only).
    """
    service = SurveyService(db)
    return service.get_surveys(skip=skip, limit=limit, is_active=is_active)


@router.get("/{survey_id}", response_model=SurveyResponse)
def get_survey(
    survey_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Get survey details with all versions (Admin only).
    """
    service = SurveyService(db)
    return service.get_survey(survey_id)


@router.put("/{survey_id}", response_model=SurveyResponse)
def update_survey(
    survey_id: int,
    survey_data: SurveyUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Update survey - creates new version if questions modified (Admin only).
    """
    service = SurveyService(db)
    return service.update_survey(survey_id, survey_data)


@router.delete("/{survey_id}", status_code=204)
def delete_survey(
    survey_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Soft delete survey (Admin only).
    """
    service = SurveyService(db)
    service.delete_survey(survey_id)


@router.post("/{survey_id}/versions/{version_id}/publish", status_code=200)
def publish_version(
    survey_id: int,
    version_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Publish a survey version (Admin only).
    
    Published versions become available to mobile app.
    """
    service = SurveyService(db)
    version = service.publish_version(version_id)
    return {"message": f"Version {version.version_number} published successfully"}
