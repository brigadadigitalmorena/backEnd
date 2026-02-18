"""Admin statistics endpoint."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Annotated

from app.core.database import get_db
from app.api.dependencies import AdminUser
from app.models.user import User, UserRole
from app.models.survey import Survey
from app.models.assignment import Assignment, AssignmentStatus
from app.models.response import SurveyResponse

router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])


@router.get("")
def get_admin_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    response: Response,
):
    """Return system-wide statistics for the admin dashboard."""
    # Allow clients and CDN-edge to cache this for 60 s.
    # "private" ensures proxies don't share it across users.
    response.headers["Cache-Control"] = "private, max-age=60"

    # Exclude soft-deleted users from all counts
    live_users = db.query(User).filter(User.deleted_at == None)  # noqa: E711

    total_users = live_users.count()

    active_brigadistas = (
        live_users
        .filter(User.role == UserRole.BRIGADISTA.value, User.is_active == True)
        .count()
    )

    active_surveys = (
        db.query(func.count(Survey.id))
        .filter(Survey.is_active == True)
        .scalar()
        or 0
    )

    total_assignments = db.query(func.count(Assignment.id)).scalar() or 0

    completed_assignments = (
        db.query(func.count(Assignment.id))
        .filter(Assignment.status == AssignmentStatus.INACTIVE.value)
        .scalar()
        or 0
    )

    pending_assignments = (
        db.query(func.count(Assignment.id))
        .filter(Assignment.status == AssignmentStatus.ACTIVE.value)
        .scalar()
        or 0
    )

    total_responses = db.query(func.count(SurveyResponse.id)).scalar() or 0

    response_rate = (
        round((completed_assignments / total_assignments) * 100, 1)
        if total_assignments > 0
        else 0.0
    )

    return {
        "totalUsers": total_users,
        "activeSurveys": active_surveys,
        "completedAssignments": completed_assignments,
        "totalResponses": total_responses,
        "pendingAssignments": pending_assignments,
        "activeBrigadistas": active_brigadistas,
        "responseRate": response_rate,
        "totalAssignments": total_assignments,
    }
