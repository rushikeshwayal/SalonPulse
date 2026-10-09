"""Owner-visible customer interaction scores by visit."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from .services import list_ratings

router = APIRouter(prefix="/api/owner/customer-ratings", tags=["Owner / Customer Ratings"], dependencies=[Depends(require_owner)])

@router.get("", summary="List customer interaction ratings across staff")
def ratings(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_ratings(db, user, limit)
