"""Owner-wide interaction rating view."""

from sqlalchemy.orm import Session
from ...common.services.ratings import list_ratings

def list_owner_ratings(db: Session, user: dict, limit: int = 50): return list_ratings(db, user, limit)
