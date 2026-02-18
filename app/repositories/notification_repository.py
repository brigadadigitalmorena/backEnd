"""Notification repository."""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:
    """Notification data access layer."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        type: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
    ) -> Notification:
        """Create a new notification."""
        notification = Notification(
            type=type,
            title=title,
            message=message,
            action_url=action_url,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_all(self, skip: int = 0, limit: int = 50, unread_only: bool = False) -> List[Notification]:
        """Get all notifications ordered by newest first."""
        query = self.db.query(Notification)
        if unread_only:
            query = query.filter(Notification.read == False)  # noqa: E712
        return (
            query.order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_unread_count(self) -> int:
        """Count unread notifications."""
        return self.db.query(Notification).filter(Notification.read == False).count()  # noqa: E712

    def mark_read(self, notification_id: int) -> Optional[Notification]:
        """Mark a single notification as read."""
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.read = True
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_all_read(self) -> int:
        """Mark all unread notifications as read. Returns number updated."""
        count = (
            self.db.query(Notification)
            .filter(Notification.read == False)  # noqa: E712
            .update({"read": True})
        )
        self.db.commit()
        return count

    def delete(self, notification_id: int) -> bool:
        """Delete a notification."""
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            self.db.delete(notification)
            self.db.commit()
            return True
        return False
