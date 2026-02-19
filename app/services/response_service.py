"""Survey response service."""
from typing import List, Dict
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.repositories.response_repository import ResponseRepository
from app.repositories.survey_repository import SurveyRepository
from app.models.response import SurveyResponse
from app.schemas.response import (
    SurveyResponseCreate, 
    BatchResponseResult, 
    ResponseValidationResult,
    ValidationStatus
)


class ResponseService:
    """Survey response business logic."""
    
    def __init__(self, db: Session):
        self.db = db
        self.response_repo = ResponseRepository(db)
        self.survey_repo = SurveyRepository(db)
    
    def submit_response(self, response_data: SurveyResponseCreate, 
                       user_id: int) -> SurveyResponse:
        """
        Submit a survey response (offline sync).
        
        Features:
        - Deduplication via client_id
        - Validates version exists
        - Creates response with all answers atomically
        
        Raises:
            HTTPException: If validation fails or duplicate
        """
        # Check for duplicate submission
        if self.response_repo.exists_by_client_id(response_data.client_id):
            # Return existing response instead of error (idempotency)
            existing = self.response_repo.get_by_client_id(response_data.client_id)
            return existing
        
        # Validate version exists
        version = self.survey_repo.get_version_by_id(response_data.version_id)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Survey version not found"
            )
        
        if not version.is_published:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot submit response to unpublished version"
            )
        
        # Create response
        try:
            response = self.response_repo.create_response(
                user_id=user_id,
                version_id=response_data.version_id,
                client_id=response_data.client_id,
                started_at=response_data.started_at,
                completed_at=response_data.completed_at,
                location=response_data.location,
                device_info=response_data.device_info
            )
            
            # Create all answers
            for answer_data in response_data.answers:
                self.response_repo.create_answer(
                    response_id=response.id,
                    question_id=answer_data.question_id,
                    answer_value=answer_data.answer_value,
                    media_url=answer_data.media_url,
                    answered_at=answer_data.answered_at
                )
            
            # Refresh to get all answers
            return self.response_repo.get_by_id(response.id)
            
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to submit response: {str(e)}"
            )
    
    def get_response(self, response_id: int) -> SurveyResponse:
        """
        Get response by ID.
        
        Raises:
            HTTPException: If response not found
        """
        response = self.response_repo.get_by_id(response_id)
        
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Response not found"
            )
        
        return response
    
    def get_user_responses(self, user_id: int, skip: int = 0, 
                          limit: int = 100) -> List[SurveyResponse]:
        """Get all responses submitted by a user."""
        return self.response_repo.get_by_user(user_id, skip=skip, limit=limit)
    
    def get_survey_responses(self, survey_id: int, skip: int = 0,
                            limit: int = 100) -> List[SurveyResponse]:
        """Get all responses for a survey (all versions)."""
        return self.response_repo.get_by_survey(survey_id, skip=skip, limit=limit)
    
    def get_version_responses(self, version_id: int, skip: int = 0,
                             limit: int = 100) -> List[SurveyResponse]:
        """Get all responses for a specific version."""
        return self.response_repo.get_by_version(version_id, skip=skip, limit=limit)

    def get_sync_status(self, user_id: int) -> dict:
        """Get sync status counters for a user."""
        synced = len(self.response_repo.get_by_user(user_id, skip=0, limit=100000))
        return {"synced_responses": synced}

    def submit_batch_responses(
        self, responses: List[SurveyResponseCreate], user_id: int
    ) -> BatchResponseResult:
        """
        Submit multiple survey responses atomically with per-item savepoints.

        Each response is protected by its own SAVEPOINT so a failure in one
        item does not roll back the items that already succeeded.  The overall
        transaction is committed once all items are processed.

        Returns:
            BatchResponseResult with per-item ValidationStatus and summary counts.
        """
        results: List[ResponseValidationResult] = []
        synced = 0
        failed_ids: List[str] = []

        for i, response_data in enumerate(responses):
            sp_name = f"sp_batch_{i}"
            try:
                # Check for duplicate before savepoint
                if self.response_repo.exists_by_client_id(response_data.client_id):
                    results.append(
                        ResponseValidationResult(
                            client_id=response_data.client_id,
                            status=ValidationStatus.DUPLICATE,
                            message="Response already synced (duplicate client_id)",
                        )
                    )
                    synced += 1  # Duplicates count as successful
                    continue

                self.db.execute(text(f"SAVEPOINT {sp_name}"))
                # Reuse single-item logic
                self.submit_response(response_data, user_id)
                self.db.execute(text(f"RELEASE SAVEPOINT {sp_name}"))
                results.append(
                    ResponseValidationResult(
                        client_id=response_data.client_id,
                        status=ValidationStatus.SYNCED,
                        message="Synced successfully",
                    )
                )
                synced += 1
            except HTTPException as exc:
                self.db.execute(text(f"ROLLBACK TO SAVEPOINT {sp_name}"))
                results.append(
                    ResponseValidationResult(
                        client_id=response_data.client_id,
                        status=ValidationStatus.FAILED,
                        message=exc.detail,
                    )
                )
                failed_ids.append(response_data.client_id)
            except Exception as exc:  # noqa: BLE001
                self.db.execute(text(f"ROLLBACK TO SAVEPOINT {sp_name}"))
                results.append(
                    ResponseValidationResult(
                        client_id=response_data.client_id,
                        status=ValidationStatus.FAILED,
                        message=str(exc),
                    )
                )
                failed_ids.append(response_data.client_id)

        # Commit all successful savepoints in one shot
        self.db.commit()

        # Count duplicates (items that were already in DB)
        duplicates = sum(
            1 for r in results if r.status == ValidationStatus.DUPLICATE
        )

        return BatchResponseResult(
            total=len(responses),
            successful=synced,
            failed=len(failed_ids),
            duplicates=duplicates,
            results=results,
        )
