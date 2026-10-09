"""Shared message-log read projection."""

from sqlalchemy.orm import Session
from ...services import message_rows

def list_messages(db: Session, user: dict, limit: int = 10) -> list[dict]:
    return message_rows(db, user, limit)
