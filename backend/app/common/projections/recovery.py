"""Recovery queue projection with visit and customer context."""

from __future__ import annotations

from sqlalchemy.orm import Session
from ..models import Barber, Branch, Customer, Feedback, RecoveryTask, Visit
from .formatting import utc_iso

def task_rows(db: Session, user: dict, limit: int = 20) -> list[dict]:
    query = db.query(RecoveryTask, Feedback, Visit, Customer, Branch, Barber).join(
        Feedback, Feedback.id == RecoveryTask.feedback_id
    ).join(Visit, Visit.id == Feedback.visit_id).join(
        Customer, Customer.id == Visit.customer_id
    ).join(Branch, Branch.id == Visit.branch_id).join(
        Barber, Barber.id == Visit.barber_id
    )
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(RecoveryTask.created_at.desc()).limit(limit).all()
    return [{
        "id": t.id, "feedback_id": f.id, "visit_id": v.id, "customer_name": c.name,
        "branch_name": b.name, "barber_name": barber.name, "rating": f.rating,
        "comment": f.comment, "status": t.status, "resolution_note": t.resolution_note,
        "created_at": utc_iso(t.created_at),
    } for t, f, v, c, b, barber in rows]
