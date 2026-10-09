"""Owner feedback operations."""

from sqlalchemy.orm import Session
from ...schemas import FeedbackCreate
from ...common.services.feedback import create_feedback, list_feedback

def list_owner_feedback(db: Session, user: dict, limit: int = 20): return list_feedback(db, user, limit)
def create_owner_feedback(db: Session, user: dict, payload: FeedbackCreate): return create_feedback(db, user, payload)
