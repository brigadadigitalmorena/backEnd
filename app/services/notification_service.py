"""Notification service."""
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.notification_repository import NotificationRepository
from app.models.notification import Notification


class NotificationService:
    """Notification business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationRepository(db)

    # ------------------------------------------------------------------
    # Factory helpers — called from other services to emit notifications
    # ------------------------------------------------------------------

    def notify_survey_created(self, survey_title: str, survey_id: int) -> Notification:
        return self.repo.create(
            type="survey_created",
            title="Nueva encuesta creada",
            message=f"Se creó la encuesta \"{survey_title}\" exitosamente.",
            action_url="/dashboard/surveys",
        )

    def notify_survey_deleted(self, survey_title: str) -> Notification:
        return self.repo.create(
            type="survey_deleted",
            title="Encuesta eliminada",
            message=f"La encuesta \"{survey_title}\" fue eliminada.",
            action_url="/dashboard/surveys",
        )

    def notify_version_published(self, survey_title: str, version_number: int, survey_id: int) -> Notification:
        return self.repo.create(
            type="version_published",
            title="Versión publicada",
            message=f"La versión {version_number} de \"{survey_title}\" fue publicada.",
            action_url=f"/dashboard/surveys",
        )

    def notify_assignment_created(self, brigadista_name: str, survey_title: str) -> Notification:
        return self.repo.create(
            type="assignment_created",
            title="Nueva asignación creada",
            message=f"{brigadista_name} fue asignado/a a la encuesta \"{survey_title}\".",
            action_url="/dashboard/assignments",
        )

    def notify_user_registered(self, user_name: str, role: str) -> Notification:
        return self.repo.create(
            type="user_registered",
            title="Nuevo usuario registrado",
            message=f"{user_name} se registró con rol \"{role}\".",
            action_url="/dashboard/users",
        )

    # ------------------------------------------------------------------
    # Read / manage notifications (used by API endpoints)
    # ------------------------------------------------------------------

    def get_notifications(
        self,
        skip: int = 0,
        limit: int = 50,
        unread_only: bool = False,
    ) -> List[Notification]:
        return self.repo.get_all(skip=skip, limit=limit, unread_only=unread_only)

    def get_unread_count(self) -> int:
        return self.repo.get_unread_count()

    def mark_read(self, notification_id: int) -> Notification:
        notification = self.repo.mark_read(notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        return notification

    def mark_all_read(self) -> int:
        return self.repo.mark_all_read()

    def delete_notification(self, notification_id: int) -> None:
        success = self.repo.delete(notification_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
