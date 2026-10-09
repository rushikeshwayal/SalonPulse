"""Owner insights from shared domain aggregates."""

from sqlalchemy.orm import Session
from ...common.services.insights import get_insights as _get_insights


def get_insights(db: Session, user: dict):
    return _get_insights(db, user)
