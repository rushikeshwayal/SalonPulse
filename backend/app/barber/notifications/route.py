"""Barber feedback notifications."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_barber
from .schema import NotificationList
from .services import list_notifications

router = APIRouter(prefix="/api/barber/notifications", tags=["Barber / Notifications"], dependencies=[Depends(require_barber)])

@router.get("", response_model=NotificationList, summary="Feedback notifications for visits served by this barber")
def notifications(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_notifications(db, user, limit)
