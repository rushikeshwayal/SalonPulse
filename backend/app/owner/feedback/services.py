"""Owner feedback operations."""

from sqlalchemy.orm import Session
from ...schemas import FeedbackCreate
from ...common.services.feedback import create_feedback as _create_feedback, list_feedback as _list_feedback


def list_feedback(db: Session, user: dict, limit: int = 20):
    return _list_feedback(db, user, limit)

def create_feedback(db: Session, user: dict, payload: FeedbackCreate):
    return _create_feedback(db, user, payload)
