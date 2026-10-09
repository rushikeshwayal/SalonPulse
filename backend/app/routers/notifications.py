"""Feedback notification endpoints. No audit information is exposed here."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Barber, Branch, Customer, Feedback, Visit
from ..services import utc_iso

router = APIRouter()


@router.get("/api/notifications")
def get_notifications(limit: int = Query(default=50, ge=1, le=100),
                      db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Show feedback received on visits visible to this account; never expose audit events here."""
    query = db.query(Feedback, Visit, Customer, Branch, Barber).join(
        Visit, Visit.id == Feedback.visit_id
    ).join(Customer, Customer.id == Visit.customer_id).join(
        Branch, Branch.id == Visit.branch_id
    ).join(Barber, Barber.id == Visit.barber_id)
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(Feedback.created_at.desc(), Feedback.id.desc()).limit(limit).all()
    visit_sequences: dict[int, tuple[int, int]] = {}
    history_rows = db.query(Visit.id, Visit.customer_id).order_by(
        Visit.completed_at.desc(), Visit.id.desc()
    ).all()
    per_customer: dict[int, list[int]] = {}
    for history_visit_id, customer_id in history_rows:
        per_customer.setdefault(customer_id, []).append(history_visit_id)
    for ids in per_customer.values():
        for index, history_visit_id in enumerate(ids):
            visit_sequences[history_visit_id] = (len(ids) - index, len(ids))

    notifications = []
    for feedback, visit, customer, branch, barber in rows:
        number, total = visit_sequences.get(visit.id, (1, 1))
        notifications.append({
            "id": "feedback-" + str(feedback.id),
            "type": "customer_feedback",
            "title": "Customer feedback received",
            "message": (feedback.comment or "").strip(),
            "customer_id": customer.id,
            "customer_name": customer.name,
            "visit_id": visit.id,
            "visit_number": number,
            "visit_count": total,
            "rating": feedback.rating,
            "service_name": visit.service_name,
            "amount": visit.amount,
            "branch_name": branch.name,
            "barber_name": barber.name,
            "created_at": utc_iso(feedback.created_at),
            "completed_at": utc_iso(visit.completed_at),
            "is_read": False,
        })
    return {
        "notifications": notifications,
        "count": len(notifications),
    }
