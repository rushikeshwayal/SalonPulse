"""Owner performance analytics."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from .services import get_insights

router = APIRouter(prefix="/api/owner/insights", tags=["Owner / Insights"], dependencies=[Depends(require_owner)])

@router.get("", summary="Performance by branch and barber")
def insights(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_insights(db, user)
