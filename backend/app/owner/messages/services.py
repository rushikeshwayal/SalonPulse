"""Owner message activity."""

from sqlalchemy.orm import Session
from ...common.services.messages import list_messages

def list_owner_messages(db: Session, user: dict, limit: int = 10): return list_messages(db, user, limit)

def list_messages(db: Session, user: dict, limit: int = 10): return list_owner_messages(db, user, limit)
