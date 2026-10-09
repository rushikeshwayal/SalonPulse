"""Owner visit workflows delegate to shared visit use-cases."""

from sqlalchemy.orm import Session
from ...common.services.visits import create_visit, get_visit_history, list_visits, update_visit
from ...schemas import VisitCreate, VisitUpdate

def list_owner_visits(db: Session, user: dict, limit: int = 20): return list_visits(db, user, limit)
def create(db: Session, user: dict, payload: VisitCreate): return create_visit(db, user, payload)
def update(db: Session, user: dict, visit_id: int, payload: VisitUpdate): return update_visit(db, user, visit_id, payload)
def history(db: Session, user: dict, visit_id: int): return get_visit_history(db, user, visit_id)

def list_visits(db: Session, user: dict, limit: int = 20): return list_owner_visits(db, user, limit)
