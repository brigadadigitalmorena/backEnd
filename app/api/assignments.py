"""Assignment router."""
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.assignment_service import AssignmentService
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, AssignmentResponse, AssignmentDetailResponse, UserMini
from app.models.assignment import AssignmentStatus
from app.models.admin_audit_log import AdminAuditLog
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
    assignments = repo.get_all(status=status, skip=skip, limit=limit)
    # Attach response_count to each assignment as a transient attribute
    for a in assignments:
        a.response_count = repo.get_response_count(a.user_id, a.survey_id)
    return assignments


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


@router.get("/by-me", response_model=List[AssignmentDetailResponse])
def get_my_created_assignments(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
    status: Optional[AssignmentStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=200)
):
    """
    Get assignments created by the current encargado (or admin).
    Filtered by assigned_by = current_user.id.
    """
    from app.repositories.assignment_repository import AssignmentRepository
    repo = AssignmentRepository(db)
    assignments = repo.get_by_assigner(current_user.id, status=status, skip=skip, limit=limit)
    for a in assignments:
        a.response_count = repo.get_response_count(a.user_id, a.survey_id)
    return assignments


@router.get("/my-team", response_model=List[UserMini])
def get_my_team(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
):
    """
    Get unique team members (brigadistas) assigned by the current encargado.
    Returns deduplicated list of users who have at least one active assignment
    created by this encargado.
    """
    from app.repositories.assignment_repository import AssignmentRepository
    repo = AssignmentRepository(db)
    assignments = repo.get_by_assigner(current_user.id, limit=200)
    seen_ids: set = set()
    team: list = []
    for a in assignments:
        if a.user and a.user.id not in seen_ids:
            seen_ids.add(a.user.id)
            team.append(a.user)
    return team


@router.get("/my-team-responses")
def get_my_team_responses(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """
    Get survey responses submitted by team members assigned by the current encargado.
    Returns a flat list ordered by most recent first.
    """
    from app.repositories.assignment_repository import AssignmentRepository
    from app.models.response import SurveyResponse
    from app.models.survey import SurveyVersion, Survey
    from app.models.user import User
    from sqlalchemy.orm import joinedload

    repo = AssignmentRepository(db)
    assignments = repo.get_by_assigner(current_user.id, limit=200)
    user_ids = list({a.user_id for a in assignments})

    if not user_ids:
        return []

    rows = (
        db.query(SurveyResponse)
        .options(
            joinedload(SurveyResponse.version).joinedload(SurveyVersion.survey),
        )
        .join(SurveyVersion, SurveyResponse.version_id == SurveyVersion.id)
        .join(Survey, SurveyVersion.survey_id == Survey.id)
        .filter(SurveyResponse.user_id.in_(user_ids))
        .order_by(SurveyResponse.completed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Fetch user names in one query
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "brigadista_name": users[r.user_id].full_name if r.user_id in users else "—",
            "survey_title": r.version.survey.title if r.version and r.version.survey else "—",
            "survey_id": r.version.survey_id if r.version else None,
            "version_id": r.version_id,
            "client_id": r.client_id,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "location": r.location,
            "answer_count": len(r.answers) if hasattr(r, "answers") else 0,
        }
        for r in rows
    ]


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
    from app.repositories.assignment_repository import AssignmentRepository
    repo = AssignmentRepository(db)
    assignment = repo.get_by_id(assignment_id)  # capture before deletion

    service = AssignmentService(db)
    service.delete_assignment(assignment_id)

    if assignment:
        db.add(AdminAuditLog(
            actor_id=current_user.id,
            action="assignment.delete",
            target_type="assignment",
            target_id=assignment_id,
            details={
                "user_id": assignment.user_id,
                "survey_id": assignment.survey_id,
                "status": assignment.status.value if hasattr(assignment.status, 'value') else str(assignment.status),
            },
        ))
        db.commit()
