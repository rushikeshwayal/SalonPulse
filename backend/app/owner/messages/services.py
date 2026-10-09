"""Owner-only message activity read service."""

from sqlalchemy.orm import Session
from ...routers.management import get_messages as _get_messages

def list_messages(db: Session, user: dict, limit: int = 10): return _get_messages(limit=limit, db=db, user=user)
