"""Owner feedback inbox and feedback-entry operations."""

from sqlalchemy.orm import Session
from ...schemas import FeedbackCreate
from ...routers.management import get_feedback as _list, submit_feedback as _create


def list_feedback(db: Session, user: dict, limit: int = 20): return _list(limit=limit, db=db, user=user)
def create_feedback(db: Session, user: dict, payload: FeedbackCreate): return _create(payload=payload, db=db, user=user)
