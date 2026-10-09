"""Owner demo reset service."""

from sqlalchemy.orm import Session
from ...common.services.demo import reset as _reset


def reset(db: Session, user: dict):
    return _reset(db, user)
