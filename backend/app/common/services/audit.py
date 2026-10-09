"""Owner-only internal audit log queries."""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from ...models import AuditLog
from ...services import utc_iso


def list_audit_logs(db: Session, user: dict, limit: int = 50) -> list[dict]:
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner access required.")
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
    return [{
        "id": row.id, "actor_user_id": row.actor_user_id,
        "actor_username": row.actor_username, "actor_role": row.actor_role,
        "action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id,
        "before_data": row.before_data, "after_data": row.after_data,
        "change_note": row.change_note, "created_at": utc_iso(row.created_at),
    } for row in rows]
