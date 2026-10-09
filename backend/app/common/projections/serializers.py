"""Shared ORM-to-JSON serializers used by routes, audit snapshots and services."""

from __future__ import annotations

from sqlalchemy.orm import Session
from ..models import Barber, Branch, Customer, Feedback, RecoveryTask, Visit, VisitService
from .formatting import utc_iso

def customer_json(db: Session, customer: Customer) -> dict:
    visits = db.query(Visit).filter_by(customer_id=customer.id)
    last = visits.order_by(Visit.completed_at.desc()).first()
    return {
        "id": customer.id, "name": customer.name, "phone": customer.phone,
        "location": customer.location or "", "messaging_consent": customer.messaging_consent,
        "visit_count": visits.count(), "last_visit": (last.completed_at.isoformat() + "Z") if last and last.completed_at.tzinfo is None else (last.completed_at.isoformat() if last else None),
    }

def visit_json(db: Session, v: Visit) -> dict:
    c, b, barber = db.get(Customer, v.customer_id), db.get(Branch, v.branch_id), db.get(Barber, v.barber_id)
    f = db.query(Feedback).filter_by(visit_id=v.id).first()
    lines = db.query(VisitService).filter_by(visit_id=v.id).order_by(VisitService.id).all()
    service_items = [
        {"service_name": x.service_name, "quantity": x.quantity,
         "unit_price": x.unit_price, "line_total": x.line_total}
        for x in lines
    ]
    return {
        "id": v.id, "customer_id": v.customer_id, "customer_name": c.name if c else "Unknown",
        "customer_phone": c.phone if c else "", "customer_location": c.location if c else "",
        "branch_id": v.branch_id, "branch_name": b.name if b else "Unknown",
        "barber_id": v.barber_id, "barber_name": barber.name if barber else "Unknown",
        "service_name": v.service_name, "service_items": service_items, "amount": v.amount,
        "completed_at": (v.completed_at.isoformat() + "Z") if v.completed_at.tzinfo is None else v.completed_at.isoformat(), "feedback_requested": v.feedback_requested,
        "feedback_received": bool(f), "rating": f.rating if f else None,
    }

def feedback_json(db: Session, f: Feedback) -> dict:
    v = db.get(Visit, f.visit_id)
    c = db.get(Customer, v.customer_id) if v else None
    b = db.get(Branch, v.branch_id) if v else None
    barber = db.get(Barber, v.barber_id) if v else None
    task = db.query(RecoveryTask).filter_by(feedback_id=f.id).first()
    return {
        "id": f.id, "visit_id": f.visit_id, "customer_name": c.name if c else "Unknown",
        "branch_name": b.name if b else "Unknown", "barber_name": barber.name if barber else "Unknown",
        "rating": f.rating, "comment": f.comment, "created_at": f.created_at.isoformat(),
        "recovery_task_id": task.id if task else None, "recovery_status": task.status if task else None,
    }

def task_json(db: Session, t: RecoveryTask) -> dict:
    f = db.get(Feedback, t.feedback_id)
    v = db.get(Visit, f.visit_id) if f else None
    c = db.get(Customer, v.customer_id) if v else None
    b = db.get(Branch, v.branch_id) if v else None
    barber = db.get(Barber, v.barber_id) if v else None
    return {
        "id": t.id, "feedback_id": t.feedback_id, "visit_id": v.id if v else None,
        "customer_name": c.name if c else "Unknown", "branch_name": b.name if b else "Unknown",
        "barber_name": barber.name if barber else "Unknown", "rating": f.rating if f else None,
        "comment": f.comment if f else "", "status": t.status, "resolution_note": t.resolution_note,
        "created_at": t.created_at.isoformat(),
    }

def visit_snapshot(db: Session, visit: Visit) -> dict:
    return visit_json(db, visit)
