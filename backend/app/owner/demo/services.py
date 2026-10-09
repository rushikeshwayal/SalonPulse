"""Owner demo reset service."""

from sqlalchemy.orm import Session
from ...common.services.demo import reset

def reset_demo(db: Session, user: dict): return reset(db, user)
