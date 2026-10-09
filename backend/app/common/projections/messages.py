"""Mock messaging activity projection scoped to the active role."""

from __future__ import annotations

from sqlalchemy.orm import Session
from ..models import Customer, MessageLog, Visit
from .formatting import utc_iso

def message_rows(db: Session, user: dict, limit: int = 10) -> list[dict]:
    query = db.query(MessageLog, Visit, Customer).join(
        Visit, Visit.id == MessageLog.visit_id
    ).join(Customer, Customer.id == Visit.customer_id)
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    return [{
        "id": m.id, "visit_id": v.id, "customer_name": c.name, "status": m.status,
        "message": m.message, "created_at": utc_iso(m.created_at), "channel": "whatsapp_mock",
    } for m, v, c in query.order_by(MessageLog.created_at.desc()).limit(limit).all()]
