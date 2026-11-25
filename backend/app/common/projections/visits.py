"""Visit list projection including per-customer visit numbering and service lines."""

from __future__ import annotations

from sqlalchemy.orm import Session
from ..models import Barber, Branch, Customer, CustomerRating, Feedback, Visit, VisitService
from .formatting import utc_iso
from .visit_history import visit_sequence_by_id

def visit_rows(db: Session, user: dict, limit: int = 20) -> list[dict]:
    query = db.query(Visit, Customer, Branch, Barber, Feedback, CustomerRating).join(
        Customer, Customer.id == Visit.customer_id
    ).join(Branch, Branch.id == Visit.branch_id).join(
        Barber, Barber.id == Visit.barber_id
    ).outerjoin(Feedback, Feedback.visit_id == Visit.id).outerjoin(
        CustomerRating, CustomerRating.visit_id == Visit.id
    )
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(Visit.completed_at.desc(), Visit.id.desc()).limit(limit).all()
    visit_ids = [v.id for v, *_ in rows]
    # Use complete customer history, not just this role's visible page.
    customer_sequence = visit_sequence_by_id(db)
    service_map: dict[int, list[dict]] = {}
    if visit_ids:
        for line in db.query(VisitService).filter(VisitService.visit_id.in_(visit_ids)).order_by(VisitService.id).all():
            service_map.setdefault(line.visit_id, []).append({
                "service_name": line.service_name, "quantity": line.quantity,
                "unit_price": line.unit_price, "line_total": line.line_total,
            })
    return [{
        "id": v.id, "customer_id": c.id, "customer_name": c.name,
        "customer_phone": c.phone, "customer_location": c.location or "",
        "branch_id": b.id, "branch_name": b.name, "barber_id": barber.id, "barber_name": barber.name,
        "service_name": v.service_name, "service_items": service_map.get(v.id, []),
        "amount": v.amount, "completed_at": utc_iso(v.completed_at),
        "feedback_requested": v.feedback_requested, "feedback_received": f is not None,
        "rating": f.rating if f else None, "feedback_comment": f.comment if f else None,
        "feedback_created_at": utc_iso(f.created_at) if f else None,
        "customer_rating": cr.rating if cr else None,
        "customer_rating_note": cr.note if cr else "",
        "visit_number": customer_sequence.get(v.id, (1, 1, False))[0],
        "visit_count": customer_sequence.get(v.id, (1, 1, False))[1],
        "is_latest_visit": customer_sequence.get(v.id, (1, 1, False))[2],
        "can_edit": (
            customer_sequence.get(v.id, (1, 1, False))[2]
            and (user["role"] == "owner" or v.barber_id == user.get("barber_id"))
        ),
    } for v, c, b, barber, f, cr in rows]
