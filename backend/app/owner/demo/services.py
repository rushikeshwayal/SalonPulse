"""Owner-only local demo reset service."""

from sqlalchemy.orm import Session
from ...routers.management import reset_demo as _reset_demo

def reset(db: Session, user: dict): return _reset_demo(user=user, db=db)
