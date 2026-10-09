"""Owner audit history."""

from sqlalchemy.orm import Session
from ...common.services.audit import list_audit_logs as _list_audit_logs


def list_audit_logs(db: Session, user: dict, limit: int = 50):
    return _list_audit_logs(db, user, limit)
