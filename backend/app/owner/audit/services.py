"""Owner-only administrative audit history."""

from sqlalchemy.orm import Session
from ...routers.management import get_audit_logs as _get_audit_logs

def list_audit_logs(db: Session, user: dict, limit: int = 50): return _get_audit_logs(limit=limit, db=db, user=user)
