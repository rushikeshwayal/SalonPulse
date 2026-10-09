"""Owner demo reset service."""

from sqlalchemy.orm import Session
from ...common.services.demo import reset

def reset_demo(db: Session, user: dict): return reset(db, user)

def reset(db: Session, user: dict): return reset_demo(db, user)
