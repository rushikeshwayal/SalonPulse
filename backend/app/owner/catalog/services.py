"""Owner reference-data application services."""

from sqlalchemy.orm import Session
from ...constants import SERVICE_CATALOG
from ...services import barber_rows, branch_rows


def list_branches(db: Session, user: dict): return branch_rows(db, user)
def list_barbers(db: Session, user: dict, branch_id: int | None = None):
    rows = barber_rows(db, user)
    return [item for item in rows if not branch_id or item["branch_id"] == branch_id]
def list_services(): return SERVICE_CATALOG
