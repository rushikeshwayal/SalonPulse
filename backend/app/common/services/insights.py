"""Shared performance aggregate projections."""

from sqlalchemy.orm import Session
from ..projections.dashboard import insight_data

def get_insights(db: Session, user: dict) -> dict:
    return insight_data(db, user)
