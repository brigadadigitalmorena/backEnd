"""Survey service."""
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.survey_repository import SurveyRepository
from app.repositories.notification_repository import NotificationRepository
from app.models.survey import Survey, SurveyVersion
from app.schemas.survey import SurveyCreate, SurveyUpdate


class SurveyService:
    """Survey business logic."""
    
    def __init__(self, db: Session):
        self.db = db
        self.survey_repo = SurveyRepository(db)
        self.notif_repo = NotificationRepository(db)
    
    def create_survey(self, survey_data: SurveyCreate, created_by: int) -> Survey:
        """
        Create a new survey with initial version.
        
        Creates survey, first version, and all questions with options.
        """
        # Create survey
        survey = self.survey_repo.create(
            title=survey_data.title,
            description=survey_data.description,
            created_by=created_by
        )
        
        # Create first version
        version = self.survey_repo.create_version(
            survey_id=survey.id,
            version_number=1,
            change_summary="Initial version"
        )
        
        # Create questions and options
        for question_data in survey_data.questions:
            question = self.survey_repo.create_question(
                version_id=version.id,
                question_text=question_data.question_text,
                question_type=question_data.question_type,
                order=question_data.order,
                is_required=question_data.is_required,
                validation_rules=question_data.validation_rules
            )
            
            # Create answer options if applicable
            if question_data.options:
                for option_data in question_data.options:
                    self.survey_repo.create_answer_option(
                        question_id=question.id,
                        option_text=option_data.option_text,
                        order=option_data.order
                    )
        
        # Refresh to get all relationships
        result = self.survey_repo.get_by_id(survey.id)

        # Emit notification
        self.notif_repo.create(
            type="survey_created",
            title="Nueva encuesta creada",
            message=f'Se creó la encuesta "{survey_data.title}" exitosamente.',
            action_url="/dashboard/surveys",
        )

        return result
    
    def get_survey(self, survey_id: int) -> Survey:
        """
        Get survey by ID.
        
        Raises:
            HTTPException: If survey not found
        """
        survey = self.survey_repo.get_by_id(survey_id)
        
        if not survey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Survey not found"
            )
        
        return survey
    
    def get_surveys(self, skip: int = 0, limit: int = 100, 
                    is_active: Optional[bool] = None) -> List[Survey]:
        """Get list of surveys."""
        return self.survey_repo.get_all(skip=skip, limit=limit, is_active=is_active)
    
    def update_survey(self, survey_id: int, survey_data: SurveyUpdate) -> Survey:
        """
        Update survey - creates a new version if questions are modified.
        
        Raises:
            HTTPException: If survey not found
        """
        survey = self.get_survey(survey_id)
        
        # Update basic fields
        kwargs: dict = {}
        if survey_data.title is not None:
            kwargs["title"] = survey_data.title
        if survey_data.description is not None:
            kwargs["description"] = survey_data.description
        if survey_data.is_active is not None:
            kwargs["is_active"] = survey_data.is_active
        if survey_data.starts_at is not None:
            kwargs["starts_at"] = survey_data.starts_at
        if survey_data.ends_at is not None:
            kwargs["ends_at"] = survey_data.ends_at
        if survey_data.estimated_duration_minutes is not None:
            kwargs["estimated_duration_minutes"] = survey_data.estimated_duration_minutes
        if survey_data.max_responses is not None:
            kwargs["max_responses"] = survey_data.max_responses
        if survey_data.allow_anonymous is not None:
            kwargs["allow_anonymous"] = survey_data.allow_anonymous
        if kwargs:
            self.survey_repo.update(survey_id=survey_id, **kwargs)
        
        # If questions are being updated, create new version
        if survey_data.questions:
            latest_version = self.survey_repo.get_latest_version(survey_id)
            new_version_number = (latest_version.version_number + 1) if latest_version else 1
            
            # Create new version
            version = self.survey_repo.create_version(
                survey_id=survey_id,
                version_number=new_version_number,
                change_summary=survey_data.change_summary or f"Version {new_version_number}"
            )
            
            # Create questions and options
            for question_data in survey_data.questions:
                question = self.survey_repo.create_question(
                    version_id=version.id,
                    question_text=question_data.question_text,
                    question_type=question_data.question_type,
                    order=question_data.order,
                    is_required=question_data.is_required,
                    validation_rules=question_data.validation_rules
                )
                
                if question_data.options:
                    for option_data in question_data.options:
                        self.survey_repo.create_answer_option(
                            question_id=question.id,
                            option_text=option_data.option_text,
                            order=option_data.order
                        )
        
        return self.survey_repo.get_by_id(survey_id)
    
    def delete_survey(self, survey_id: int) -> None:
        """
        Soft delete survey.
        
        Raises:
            HTTPException: If survey not found
        """
        # Fetch title before deleting for notification
        survey = self.survey_repo.get_by_id(survey_id)
        if not survey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Survey not found"
            )
        survey_title = survey.title

        success = self.survey_repo.delete(survey_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Survey not found"
            )

        # Emit notification
        self.notif_repo.create(
            type="survey_deleted",
            title="Encuesta eliminada",
            message=f'La encuesta "{survey_title}" fue eliminada.',
            action_url="/dashboard/surveys",
        )
    
    def publish_version(self, version_id: int) -> SurveyVersion:
        """
        Publish a survey version.
        
        Raises:
            HTTPException: If version not found
        """
        version = self.survey_repo.publish_version(version_id)

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Survey version not found"
            )

        # Emit notification
        survey = self.survey_repo.get_by_id(version.survey_id, include_versions=False)
        survey_title = survey.title if survey else "Encuesta"
        self.notif_repo.create(
            type="version_published",
            title="Versión publicada",
            message=f'La versión {version.version_number} de "{survey_title}" fue publicada.',
            action_url="/dashboard/surveys",
        )

        return version
    
    def get_latest_published_version(self, survey_id: int) -> SurveyVersion:
        """
        Get latest published version for mobile app.
        
        Raises:
            HTTPException: If no published version found
        """
        latest = self.survey_repo.get_latest_published_version(survey_id)
        
        if not latest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No published version available"
            )
        
        return latest
