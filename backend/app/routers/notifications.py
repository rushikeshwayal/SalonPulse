"""Legacy notifications API path retained as a compatibility adapter."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..common.services.notifications import list_notifications
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter()

@router.get("/api/notifications")
def notifications_compat(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db),
                         user: dict = Depends(get_current_user)):
    return list_notifications(db, user, limit)
