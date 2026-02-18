"""Response analytics router (Admin)."""
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from app.core.database import get_db
from app.services.response_service import ResponseService
from app.schemas.response import SurveyResponseDetail
from app.api.dependencies import AdminOrEncargado
from app.models.response import SurveyResponse, QuestionAnswer
from app.models.survey import Survey, SurveyVersion, Question

router = APIRouter(prefix="/admin/responses", tags=["Admin - Responses"])


@router.get("/summary")
def get_responses_summary(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
    date_from: Optional[date] = Query(None, description="Filter surveys by first response on or after this date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Filter surveys by last response on or before this date (YYYY-MM-DD)"),
):
    """
    Get per-survey response counts for the reports page.
    Returns each survey with total responses, version count, and last response date.
    Optionally filter by date range (date_from / date_to).
    """
    query = (
        db.query(
            Survey.id.label("survey_id"),
            Survey.title.label("survey_title"),
            Survey.is_active.label("is_active"),
            func.count(SurveyResponse.id).label("total_responses"),
            func.max(SurveyResponse.completed_at).label("last_response_at"),
        )
        .outerjoin(SurveyVersion, SurveyVersion.survey_id == Survey.id)
        .outerjoin(SurveyResponse, SurveyResponse.version_id == SurveyVersion.id)
    )

    if date_from:
        query = query.filter(
            (SurveyResponse.completed_at == None) |  # noqa: E711
            (func.date(SurveyResponse.completed_at) >= date_from)
        )
    if date_to:
        query = query.filter(
            (SurveyResponse.completed_at == None) |  # noqa: E711
            (func.date(SurveyResponse.completed_at) <= date_to)
        )

    rows = (
        query
        .group_by(Survey.id, Survey.title, Survey.is_active)
        .order_by(func.count(SurveyResponse.id).desc())
        .all()
    )

    return [
        {
            "survey_id": r.survey_id,
            "survey_title": r.survey_title,
            "is_active": r.is_active,
            "total_responses": r.total_responses,
            "last_response_at": r.last_response_at.isoformat() if r.last_response_at else None,
        }
        for r in rows
    ]


@router.get("/survey/{survey_id}/export")
def get_survey_responses_export(
    survey_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
):
    """
    Get all answers for a survey, enriched with question_text and question_type.
    Used for detailed data-analysis export (one row per answer).
    Returns: list of flat answer rows with survey/response/question context.
    """
    rows = (
        db.query(
            Survey.id.label("survey_id"),
            Survey.title.label("survey_title"),
            SurveyResponse.id.label("response_id"),
            SurveyResponse.user_id.label("user_id"),
            SurveyResponse.client_id.label("client_id"),
            SurveyResponse.completed_at.label("completed_at"),
            SurveyResponse.started_at.label("started_at"),
            SurveyResponse.location.label("location"),
            Question.id.label("question_id"),
            Question.question_text.label("question_text"),
            Question.question_type.label("question_type"),
            Question.order.label("question_order"),
            QuestionAnswer.answer_value.label("answer_value"),
            QuestionAnswer.media_url.label("media_url"),
            QuestionAnswer.answered_at.label("answered_at"),
        )
        .join(SurveyVersion, SurveyVersion.survey_id == Survey.id)
        .join(SurveyResponse, SurveyResponse.version_id == SurveyVersion.id)
        .join(QuestionAnswer, QuestionAnswer.response_id == SurveyResponse.id)
        .join(Question, Question.id == QuestionAnswer.question_id)
        .filter(Survey.id == survey_id)
        .order_by(SurveyResponse.completed_at.desc(), Question.order.asc())
        .all()
    )

    return [
        {
            "survey_id": r.survey_id,
            "survey_title": r.survey_title,
            "response_id": r.response_id,
            "user_id": r.user_id,
            "client_id": r.client_id,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "location": r.location,
            "question_id": r.question_id,
            "question_text": r.question_text,
            "question_type": r.question_type,
            "question_order": r.question_order,
            "answer_value": r.answer_value,
            "media_url": r.media_url,
            "answered_at": r.answered_at.isoformat() if r.answered_at else None,
        }
        for r in rows
    ]


@router.get("/survey/{survey_id}/timeline")
def get_survey_responses_timeline(
    survey_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
):
    """
    Get response counts grouped by date for a survey.
    Used for timeline chart on the reports page.
    """
    rows = (
        db.query(
            func.date(SurveyResponse.completed_at).label("date"),
            func.count(SurveyResponse.id).label("count"),
        )
        .join(SurveyVersion, SurveyVersion.id == SurveyResponse.version_id)
        .filter(SurveyVersion.survey_id == survey_id)
        .group_by(func.date(SurveyResponse.completed_at))
        .order_by(func.date(SurveyResponse.completed_at).asc())
        .all()
    )

    return [
        {"date": str(r.date), "count": r.count}
        for r in rows
    ]


@router.get("/survey/{survey_id}", response_model=List[SurveyResponseDetail])
def get_survey_responses(
    survey_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """
    Get all responses for a survey (Admin or Encargado).
    """
    service = ResponseService(db)
    return service.get_survey_responses(survey_id, skip=skip, limit=limit)


@router.get("/version/{version_id}", response_model=List[SurveyResponseDetail])
def get_version_responses(
    version_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """
    Get all responses for a specific survey version (Admin or Encargado).
    """
    service = ResponseService(db)
    return service.get_version_responses(version_id, skip=skip, limit=limit)


@router.get("/{response_id}", response_model=SurveyResponseDetail)
def get_response(
    response_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminOrEncargado
):
    """
    Get response details (Admin or Encargado).
    """
    service = ResponseService(db)
    return service.get_response(response_id)
