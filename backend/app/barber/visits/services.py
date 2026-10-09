"""Barber visit workflows delegate to shared visit use-cases."""

from sqlalchemy.orm import Session
from ...common.services.visits import (
    create_visit as _create_visit, get_visit_history as _get_visit_history,
    list_visits as _list_visits, update_visit as _update_visit,
)
from ...schemas import VisitCreate, VisitUpdate


def list_visits(db: Session, user: dict, limit: int = 20):
    return _list_visits(db, user, limit)

def create(db: Session, user: dict, payload: VisitCreate):
    return _create_visit(db, user, payload)

def update(db: Session, user: dict, visit_id: int, payload: VisitUpdate):
    return _update_visit(db, user, visit_id, payload)

def history(db: Session, user: dict, visit_id: int):
    return _get_visit_history(db, user, visit_id)
