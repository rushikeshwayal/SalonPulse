"""Owner feedback inbox projection with related visit, branch, barber and recovery data."""

from __future__ import annotations

from sqlalchemy.orm import Session
from ..models import Barber, Branch, Customer, Feedback, RecoveryTask, Visit
from .formatting import utc_iso

def feedback_rows(db: Session, user: dict, limit: int = 20) -> list[dict]:
    query = db.query(Feedback, Visit, Customer, Branch, Barber, RecoveryTask).join(
        Visit, Visit.id == Feedback.visit_id
    ).join(Customer, Customer.id == Visit.customer_id).join(
        Branch, Branch.id == Visit.branch_id
    ).join(Barber, Barber.id == Visit.barber_id).outerjoin(
        RecoveryTask, RecoveryTask.feedback_id == Feedback.id
    )
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(Feedback.created_at.desc()).limit(limit).all()
    return [{
        "id": f.id, "visit_id": v.id, "customer_name": c.name, "branch_name": b.name,
        "barber_name": barber.name, "rating": f.rating, "comment": f.comment,
        "created_at": utc_iso(f.created_at), "recovery_task_id": t.id if t else None,
        "recovery_status": t.status if t else None,
    } for f, v, c, b, barber, t in rows]
