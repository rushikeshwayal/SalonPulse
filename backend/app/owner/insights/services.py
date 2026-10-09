"""Owner insights from shared domain aggregates."""

from sqlalchemy.orm import Session
from ...common.services.insights import get_insights

def get_owner_insights(db: Session, user: dict): return get_insights(db, user)
