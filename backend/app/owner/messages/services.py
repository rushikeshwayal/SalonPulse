"""Owner message activity."""

from sqlalchemy.orm import Session
from ...common.services.messages import list_messages as _list_messages


def list_messages(db: Session, user: dict, limit: int = 10):
    return _list_messages(db, user, limit)
