"""Audit event writer and the role-safe initial audit projection."""

from __future__ import annotations

from typing import Optional
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from ..models import AuditLog, Visit
from .formatting import utc_iso

def add_audit(db: Session, actor: dict, action: str, entity_type: str, entity_id: int,
              before_data: Optional[dict], after_data: Optional[dict], change_note: str = "") -> None:
    db.add(AuditLog(
        actor_user_id=actor["id"], actor_username=actor["username"], actor_role=actor["role"],
        action=action, entity_type=entity_type, entity_id=entity_id,
        before_data=before_data, after_data=after_data, change_note=change_note,
    ))

def audit_logs_initial(db: Session, user: dict) -> list[dict]:
    query = db.query(AuditLog)
    if user["role"] == "barber":
        ids = db.query(Visit.id).filter(Visit.barber_id == user["barber_id"]).subquery()
        query = query.filter(or_(
            AuditLog.actor_user_id == user["id"],
            and_(AuditLog.entity_type == "visit", AuditLog.entity_id.in_(ids)),
        ))
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(20).all()
    return [{
        "id": r.id, "actor_username": r.actor_username, "actor_role": r.actor_role,
        "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
        "change_note": r.change_note, "created_at": utc_iso(r.created_at),
    } for r in rows]
