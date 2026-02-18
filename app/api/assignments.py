"""Assignment router."""
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.assignment_service import AssignmentService
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, AssignmentResponse, AssignmentDetailResponse
from app.models.assignment import AssignmentStatus
from app.api.dependencies import AdminOrEncargado, BrigadistaUser

router = APIRouter(prefix="/assignments", tags=["Assignments"])


@router.get("", response_model=List[AssignmentDetailResponse])
def list_assignments(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
    status: Optional[AssignmentStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=200)
):
    """
    List all assignments (Admin or Encargado) with user and survey details.
    """
    from app.repositories.assignment_repository import AssignmentRepository
    repo = AssignmentRepository(db)
    return repo.get_all(status=status, skip=skip, limit=limit)


@router.post("", response_model=AssignmentResponse, status_code=201)
def create_assignment(
    assignment_data: AssignmentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado
):
    """
    Create an assignment (Admin or Encargado).
    
    Assigns a survey to a brigadista.
    """
    service = AssignmentService(db)
    return service.create_assignment(assignment_data, current_user.id)


@router.get("/me", response_model=List[AssignmentResponse])
def get_my_assignments(
    db: Annotated[Session, Depends(get_db)],
    current_user: BrigadistaUser,
    status: Optional[AssignmentStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """
    Get current user's assignments (Brigadista only).
    """
    service = AssignmentService(db)
    return service.get_user_assignments(
        current_user.id, 
        status=status, 
        skip=skip, 
        limit=limit
    )


@router.get("/user/{user_id}", response_model=List[AssignmentResponse])
def get_user_assignments(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
    status: Optional[AssignmentStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """
    Get assignments for a specific user (Admin or Encargado).
    """
    service = AssignmentService(db)
    return service.get_user_assignments(user_id, status=status, skip=skip, limit=limit)


@router.get("/survey/{survey_id}", response_model=List[AssignmentResponse])
def get_survey_assignments(
    survey_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
    status: Optional[AssignmentStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """
    Get assignments for a specific survey (Admin or Encargado).
    """
    service = AssignmentService(db)
    return service.get_survey_assignments(survey_id, status=status, skip=skip, limit=limit)


@router.patch("/{assignment_id}", response_model=AssignmentResponse)
def update_assignment(
    assignment_id: int,
    assignment_data: AssignmentUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado
):
    """
    Update assignment (Admin or Encargado).
    """
    service = AssignmentService(db)
    return service.update_assignment(assignment_id, assignment_data)


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado
):
    """
    Delete assignment (Admin or Encargado).
    """
    service = AssignmentService(db)
    service.delete_assignment(assignment_id)
