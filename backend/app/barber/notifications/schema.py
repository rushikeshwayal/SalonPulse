"""Response schemas for feedback notifications."""

from typing import Any
from pydantic import BaseModel, Field

class NotificationList(BaseModel):
    notifications: list[dict[str, Any]] = Field(default_factory=list)
    count: int
