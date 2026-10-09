"""Legacy /api visit routes retained as compatibility adapters."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..common.services.visits import create_visit, get_dashboard, get_visit_history, list_visits, update_visit
from ..database import get_db
from ..dependencies import get_current_user
from ..schemas import VisitCreate, VisitUpdate

router = APIRouter()

@router.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_dashboard(db, user)

@router.get("/api/visits")
def get_visits(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db),
               user: dict = Depends(get_current_user)):
    return list_visits(db, user, limit)

@router.get("/api/visits/{visit_id}/history")
def get_visit_history_compat(visit_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_visit_history(db, user, visit_id)

@router.patch("/api/visits/{visit_id}")
def update_visit_compat(visit_id: int, payload: VisitUpdate, db: Session = Depends(get_db),
                        user: dict = Depends(get_current_user)):
    return update_visit(db, user, visit_id, payload)

@router.post("/api/visits", status_code=201)
def create_visit_compat(payload: VisitCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return create_visit(db, user, payload)
