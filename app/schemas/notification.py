"""Notification schemas."""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    message: str
    read: bool
    action_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    unread_count: int


class UnreadCountResponse(BaseModel):
    count: int
