"""Owner staff directory."""

from sqlalchemy.orm import Session
from ...common.services.staff import list_staff as _list_staff


def list_staff(db: Session, user: dict):
    return _list_staff(db, user)
