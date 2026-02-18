"""Assignment service."""
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.user_repository import UserRepository
from app.repositories.survey_repository import SurveyRepository
from app.repositories.notification_repository import NotificationRepository
from app.models.assignment import Assignment, AssignmentStatus
from app.models.user import UserRole
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate


class AssignmentService:
    """Assignment business logic."""
    
    def __init__(self, db: Session):
        self.db = db
        self.assignment_repo = AssignmentRepository(db)
        self.user_repo = UserRepository(db)
        self.survey_repo = SurveyRepository(db)
        self.notif_repo = NotificationRepository(db)
    
    def create_assignment(self, assignment_data: AssignmentCreate, 
                         assigned_by: int) -> Assignment:
        """
        Create a new assignment.
        
        Validates:
        - User exists and is a brigadista
        - Survey exists and is active
        - No duplicate assignment
        
        Raises:
            HTTPException: If validation fails
        """
        # Validate user
        user = self.user_repo.get_by_id(assignment_data.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.role != UserRole.BRIGADISTA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only assign surveys to brigadistas"
            )
        
        # Validate survey
        survey = self.survey_repo.get_by_id(assignment_data.survey_id, include_versions=False)
        if not survey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Survey not found"
            )
        
        if not survey.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign inactive survey"
            )
        
        # Check for duplicate
        if self.assignment_repo.exists(assignment_data.user_id, assignment_data.survey_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already assigned to this survey"
            )
        
        assignment = self.assignment_repo.create(
            user_id=assignment_data.user_id,
            survey_id=assignment_data.survey_id,
            assigned_by=assigned_by,
            location=assignment_data.location
        )

        # Emit notification
        brigadista_name = f"{user.nombre} {user.apellido}".strip() if (user.nombre or user.apellido) else user.email
        self.notif_repo.create(
            type="assignment_created",
            title="Nueva asignación creada",
            message=f'{brigadista_name} fue asignado/a a la encuesta "{survey.title}".',
            action_url="/dashboard/assignments",
        )

        return assignment
    
    def get_assignment(self, assignment_id: int) -> Assignment:
        """
        Get assignment by ID.
        
        Raises:
            HTTPException: If assignment not found
        """
        assignment = self.assignment_repo.get_by_id(assignment_id)
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
        
        return assignment
    
    def get_user_assignments(self, user_id: int, status: Optional[AssignmentStatus] = None,
                            skip: int = 0, limit: int = 100) -> List[Assignment]:
        """Get assignments for a specific user."""
        return self.assignment_repo.get_by_user(user_id, status=status, skip=skip, limit=limit)
    
    def get_survey_assignments(self, survey_id: int, status: Optional[AssignmentStatus] = None,
                              skip: int = 0, limit: int = 100) -> List[Assignment]:
        """Get assignments for a specific survey."""
        return self.assignment_repo.get_by_survey(survey_id, status=status, skip=skip, limit=limit)
    
    def update_assignment(self, assignment_id: int, 
                         assignment_data: AssignmentUpdate) -> Assignment:
        """
        Update assignment.
        
        Raises:
            HTTPException: If assignment not found
        """
        assignment = self.assignment_repo.update(
            assignment_id, 
            **assignment_data.model_dump(exclude_unset=True)
        )
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
        
        return assignment
    
    def delete_assignment(self, assignment_id: int) -> None:
        """
        Delete assignment.
        
        Raises:
            HTTPException: If assignment not found
        """
        success = self.assignment_repo.delete(assignment_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
