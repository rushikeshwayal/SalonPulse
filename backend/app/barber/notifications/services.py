"""Feedback notifications scoped to the signed-in barber's visits."""

from sqlalchemy.orm import Session
from ...routers.notifications import get_notifications as _get_notifications

def list_notifications(db: Session, user: dict, limit: int = 50):
    return _get_notifications(limit=limit, db=db, user=user)
