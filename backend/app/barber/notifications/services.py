"""Barber-only feedback notifications."""

from sqlalchemy.orm import Session
from ...common.services.notifications import list_notifications

def list_notifications_for_barber(db: Session, user: dict, limit: int = 50): return list_notifications(db, user, limit)

def list_notifications(db: Session, user: dict, limit: int = 50): return list_notifications_for_barber(db, user, limit)
