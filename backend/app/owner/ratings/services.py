"""Owner-wide interaction rating view."""

from sqlalchemy.orm import Session
from ...common.services.ratings import list_ratings as _list_ratings


def list_ratings(db: Session, user: dict, limit: int = 50):
    return _list_ratings(db, user, limit)
