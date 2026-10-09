"""Owner visit operations. The shared visit workflow owns the business rules."""

from sqlalchemy.orm import Session
from ...schemas import VisitCreate, VisitUpdate
from ...routers.visits import create_visit as _create, get_visit_history as _history, get_visits as _list, update_visit as _update


def list_visits(db: Session, user: dict, limit: int = 20): return _list(limit=limit, db=db, user=user)
def create(db: Session, user: dict, payload: VisitCreate): return _create(payload=payload, db=db, user=user)
def update(db: Session, user: dict, visit_id: int, payload: VisitUpdate): return _update(visit_id=visit_id, payload=payload, db=db, user=user)
def history(db: Session, user: dict, visit_id: int): return _history(visit_id=visit_id, db=db, user=user)
