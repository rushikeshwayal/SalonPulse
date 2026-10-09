"""Owner audit history."""

from sqlalchemy.orm import Session
from ...common.services.audit import list_audit_logs

def list_owner_audit_logs(db: Session, user: dict, limit: int = 50): return list_audit_logs(db, user, limit)
