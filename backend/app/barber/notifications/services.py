"""Barber-only feedback notifications."""

from sqlalchemy.orm import Session
from ...common.services.notifications import list_notifications as _list_notifications


def list_notifications(db: Session, user: dict, limit: int = 50):
    return _list_notifications(db, user, limit)
