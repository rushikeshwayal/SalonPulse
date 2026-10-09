"""Read-only business-wide view of barber interaction ratings."""

from sqlalchemy.orm import Session
from ...routers.management import get_customer_ratings as _get_customer_ratings

def list_ratings(db: Session, user: dict, limit: int = 50): return _get_customer_ratings(limit=limit, db=db, user=user)
