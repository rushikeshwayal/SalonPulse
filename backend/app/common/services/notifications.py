"""Barber feedback-notification query. It never exposes internal audit events."""

from sqlalchemy.orm import Session
from ...models import Barber, Branch, Customer, Feedback, Visit
from ..projections.formatting import utc_iso
from ..projections.visit_history import visit_sequence_by_id


def list_notifications(db: Session, user: dict, limit: int = 50) -> dict:
    """Show feedback received on visits visible to this account; never expose audit events here."""
    query = db.query(Feedback, Visit, Customer, Branch, Barber).join(
        Visit, Visit.id == Feedback.visit_id
    ).join(Customer, Customer.id == Visit.customer_id).join(
        Branch, Branch.id == Visit.branch_id
    ).join(Barber, Barber.id == Visit.barber_id)
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(Feedback.created_at.desc(), Feedback.id.desc()).limit(limit).all()
    visit_sequences = visit_sequence_by_id(db)

    notifications = []
    for feedback, visit, customer, branch, barber in rows:
        number, total, _is_latest = visit_sequences.get(visit.id, (1, 1, False))
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
