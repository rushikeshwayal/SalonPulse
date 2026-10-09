"""Internal audit log. This group is not exposed to barber accounts."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from .services import list_audit_logs

router = APIRouter(prefix="/api/owner/audit-logs", tags=["Owner / Audit"], dependencies=[Depends(require_owner)])

@router.get("", summary="View internal audit events")
def audit_logs(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_audit_logs(db, user, limit)
