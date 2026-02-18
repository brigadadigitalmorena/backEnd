"""Notifications router (Admin only)."""
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationResponse, NotificationListResponse, UnreadCountResponse
from app.api.dependencies import AdminUser

router = APIRouter(prefix="/admin/notifications", tags=["Admin - Notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = Query(False),
):
    """Get all notifications with unread count (Admin only)."""
    service = NotificationService(db)
    notifications = service.get_notifications(skip=skip, limit=limit, unread_only=unread_only)
    unread_count = service.get_unread_count()
    return NotificationListResponse(
        notifications=notifications,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
):
    """Get unread notification count — used for polling badge (Admin only)."""
    service = NotificationService(db)
    return UnreadCountResponse(count=service.get_unread_count())


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
):
    """Mark a single notification as read (Admin only)."""
    service = NotificationService(db)
    return service.mark_read(notification_id)


@router.patch("/read-all", response_model=dict)
def mark_all_read(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
):
    """Mark all notifications as read (Admin only)."""
    service = NotificationService(db)
    count = service.mark_all_read()
    return {"updated": count}


@router.delete("/{notification_id}", status_code=204)
def delete_notification(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
):
    """Delete a notification (Admin only)."""
    service = NotificationService(db)
    service.delete_notification(notification_id)
