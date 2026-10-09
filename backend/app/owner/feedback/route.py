"""Owner-only customer feedback management."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from ...schemas import FeedbackCreate
from .services import create_feedback, list_feedback

router = APIRouter(prefix="/api/owner/feedback", tags=["Owner / Feedback"], dependencies=[Depends(require_owner)])

@router.get("", summary="Review feedback submitted by customers")
def feedback(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_feedback(db, user, limit)

@router.post("", status_code=201, summary="Record feedback in the management workflow")
def submit(payload: FeedbackCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return create_feedback(db, user, payload)
