"""Owner-only branch and employee performance projections."""

from sqlalchemy.orm import Session
from ...services import insight_data

def get_insights(db: Session, user: dict): return insight_data(db, user)
