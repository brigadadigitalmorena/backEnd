"""Response repository."""
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from app.models.response import SurveyResponse, QuestionAnswer


class ResponseRepository:
    """Survey response data access layer."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_response(self, user_id: int, version_id: int, client_id: str,
                       completed_at, started_at=None, location=None, 
                       device_info=None) -> SurveyResponse:
        """Create a survey response."""
        response = SurveyResponse(
            user_id=user_id,
            version_id=version_id,
            client_id=client_id,
            started_at=started_at,
            completed_at=completed_at,
            location=location,
            device_info=device_info
        )
        self.db.add(response)
        self.db.commit()
        self.db.refresh(response)
        return response
    
    def get_by_id(self, response_id: int) -> Optional[SurveyResponse]:
        """Get response by ID with answers."""
        return self.db.query(SurveyResponse)\
            .options(joinedload(SurveyResponse.answers))\
            .filter(SurveyResponse.id == response_id)\
            .first()
    
    def get_by_client_id(self, client_id: str) -> Optional[SurveyResponse]:
        """Get response by client ID (for deduplication)."""
        return self.db.query(SurveyResponse)\
            .filter(SurveyResponse.client_id == client_id)\
            .first()
    
    def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[SurveyResponse]:
        """Get all responses by user."""
        return self.db.query(SurveyResponse)\
            .filter(SurveyResponse.user_id == user_id)\
            .offset(skip).limit(limit)\
            .all()
    
    def get_by_version(self, version_id: int, skip: int = 0, limit: int = 100) -> List[SurveyResponse]:
        """Get all responses for a survey version."""
        return self.db.query(SurveyResponse)\
            .filter(SurveyResponse.version_id == version_id)\
            .offset(skip).limit(limit)\
            .all()
    
    def get_by_survey(self, survey_id: int, skip: int = 0, limit: int = 100) -> List[SurveyResponse]:
        """Get all responses for a survey (any version)."""
        from app.models.survey import SurveyVersion
        
        return self.db.query(SurveyResponse)\
            .join(SurveyVersion)\
            .filter(SurveyVersion.survey_id == survey_id)\
            .offset(skip).limit(limit)\
            .all()
    
    def create_answer(self, response_id: int, question_id: int, 
                     answered_at, answer_value=None, media_url=None) -> QuestionAnswer:
        """Create a question answer."""
        answer = QuestionAnswer(
            response_id=response_id,
            question_id=question_id,
            answer_value=answer_value,
            media_url=media_url,
            answered_at=answered_at
        )
        self.db.add(answer)
        self.db.commit()
        self.db.refresh(answer)
        return answer
    
    def exists_by_client_id(self, client_id: str) -> bool:
        """Check if response exists by client ID."""
        return self.db.query(SurveyResponse)\
            .filter(SurveyResponse.client_id == client_id)\
            .first() is not None
    
    def count_by_user(self, user_id: int) -> int:
        """Count responses by user."""
        return self.db.query(SurveyResponse)\
            .filter(SurveyResponse.user_id == user_id)\
            .count()
