"""Survey repository."""
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload, subqueryload
from sqlalchemy import and_

from app.models.survey import Survey, SurveyVersion, Question, AnswerOption


class SurveyRepository:
    """Survey data access layer."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, title: str, description: Optional[str], created_by: int) -> Survey:
        """Create a new survey."""
        survey = Survey(
            title=title,
            description=description,
            created_by=created_by
        )
        self.db.add(survey)
        self.db.commit()
        self.db.refresh(survey)
        return survey
    
    def get_by_id(self, survey_id: int, include_versions: bool = True) -> Optional[Survey]:
        """Get survey by ID with optional versions."""
        query = self.db.query(Survey)
        
        if include_versions:
            query = query.options(
                joinedload(Survey.versions)
                .joinedload(SurveyVersion.questions)
                .joinedload(Question.options)
            )
        
        return query.filter(Survey.id == survey_id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100,
                is_active: Optional[bool] = None) -> List[Survey]:
        """Get all surveys with versions, questions and options (no N+1)."""
        query = self.db.query(Survey).options(
            subqueryload(Survey.versions)
            .subqueryload(SurveyVersion.questions)
            .subqueryload(Question.options)
        )

        if is_active is not None:
            query = query.filter(Survey.is_active == is_active)

        return query.order_by(Survey.created_at.desc()).offset(skip).limit(limit).all()
    
    def update(self, survey_id: int, **kwargs) -> Optional[Survey]:
        """Update survey fields."""
        survey = self.get_by_id(survey_id, include_versions=False)
        if not survey:
            return None
        
        for key, value in kwargs.items():
            if value is not None and hasattr(survey, key):
                setattr(survey, key, value)
        
        self.db.commit()
        self.db.refresh(survey)
        return survey
    
    def delete(self, survey_id: int) -> bool:
        """Soft delete survey."""
        survey = self.get_by_id(survey_id, include_versions=False)
        if not survey:
            return False
        
        survey.is_active = False
        self.db.commit()
        return True
    
    # Survey Version operations
    def create_version(self, survey_id: int, version_number: int, 
                      change_summary: Optional[str] = None) -> SurveyVersion:
        """Create a new survey version."""
        version = SurveyVersion(
            survey_id=survey_id,
            version_number=version_number,
            change_summary=change_summary
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version
    
    def get_version_by_id(self, version_id: int) -> Optional[SurveyVersion]:
        """Get survey version by ID."""
        return self.db.query(SurveyVersion)\
            .options(
                joinedload(SurveyVersion.questions)
                .joinedload(Question.options)
            )\
            .filter(SurveyVersion.id == version_id)\
            .first()
    
    def get_latest_version(self, survey_id: int) -> Optional[SurveyVersion]:
        """Get latest version of a survey."""
        return self.db.query(SurveyVersion)\
            .filter(SurveyVersion.survey_id == survey_id)\
            .order_by(SurveyVersion.version_number.desc())\
            .first()
    
    def publish_version(self, version_id: int) -> Optional[SurveyVersion]:
        """Publish a survey version."""
        version = self.get_version_by_id(version_id)
        if not version:
            return None
        
        version.is_published = True
        self.db.commit()
        self.db.refresh(version)
        return version
    
    # Question operations
    def create_question(self, version_id: int, question_text: str, 
                       question_type: str, order: int, is_required: bool = False,
                       validation_rules: Optional[dict] = None) -> Question:
        """Create a question."""
        question = Question(
            version_id=version_id,
            question_text=question_text,
            question_type=question_type,
            order=order,
            is_required=is_required,
            validation_rules=validation_rules
        )
        self.db.add(question)
        self.db.commit()
        self.db.refresh(question)
        return question
    
    def create_answer_option(self, question_id: int, option_text: str, 
                            order: int) -> AnswerOption:
        """Create an answer option."""
        option = AnswerOption(
            question_id=question_id,
            option_text=option_text,
            order=order
        )
        self.db.add(option)
        self.db.commit()
        self.db.refresh(option)
        return option
