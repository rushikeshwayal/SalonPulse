"""Owner visit list, creation, editing and version history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from ...schemas import VisitCreate, VisitUpdate
from .services import create, history, list_visits, update

router = APIRouter(prefix="/api/owner/visits", tags=["Owner / Visits"], dependencies=[Depends(require_owner)])

@router.get("", summary="List visits across all branches")
def visits(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_visits(db, user, limit)

@router.post("", status_code=201, summary="Record a customer visit")
def create_visit(payload: VisitCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return create(db, user, payload)

@router.patch("/{visit_id}", summary="Edit the latest customer visit")
def update_visit(visit_id: int, payload: VisitUpdate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return update(db, user, visit_id, payload)

@router.get("/{visit_id}/history", summary="Get saved versions and audit history for a visit")
def visit_history(visit_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return history(db, user, visit_id)
