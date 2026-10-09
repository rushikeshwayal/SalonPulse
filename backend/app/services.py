"""Reusable domain operations, data projections and response serializers."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Optional

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from .constants import SERVICE_CATALOG
from .models import (
    AuditLog, Barber, Branch, Customer, CustomerRating, Feedback, MessageLog,
    RecoveryTask, StaffUser, Visit, VisitService,
)


def add_audit(db: Session, actor: dict, action: str, entity_type: str, entity_id: int,
              before_data: Optional[dict], after_data: Optional[dict], change_note: str = "") -> None:
    db.add(AuditLog(
        actor_user_id=actor["id"], actor_username=actor["username"], actor_role=actor["role"],
        action=action, entity_type=entity_type, entity_id=entity_id,
        before_data=before_data, after_data=after_data, change_note=change_note,
    ))

def normalize_phone(value: str | None) -> str:
    digits = re.sub("[^0-9]", "", value or "")
    # Treat Indian 10-digit numbers and +91-prefixed numbers as the same phone.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def utc_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def customer_json(db: Session, customer: Customer) -> dict:
    visits = db.query(Visit).filter_by(customer_id=customer.id)
    last = visits.order_by(Visit.completed_at.desc()).first()
    return {
        "id": customer.id, "name": customer.name, "phone": customer.phone,
        "location": customer.location or "", "messaging_consent": customer.messaging_consent,
        "visit_count": visits.count(), "last_visit": (last.completed_at.isoformat() + "Z") if last and last.completed_at.tzinfo is None else (last.completed_at.isoformat() if last else None),
    }

def message_for(name: str) -> str:
    first = (name or "there").split()[0]
    return (
        f"Hi {first}, thanks for visiting us today. We'd appreciate your honest feedback "
        "about your experience. Your feedback is shared with salon management so we can improve. "
        "Reply with a rating from 1 to 5. You can opt out of future messages at any time."
    )


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

def branch_id_for_user(db: Session, user: dict) -> Optional[int]:
    if user["role"] == "owner":
        return None
    barber = db.get(Barber, user.get("barber_id"))
    return barber.branch_id if barber else None


def check_visit_access(visit: Visit, user: dict) -> None:
    if user["role"] == "barber" and visit.barber_id != user.get("barber_id"):
        raise HTTPException(status_code=403, detail="You can only access visits assigned to your barber account.")


def latest_customer_visit_id(db: Session, customer_id: int) -> Optional[int]:
    latest = db.query(Visit.id).filter(
        Visit.customer_id == customer_id
    ).order_by(Visit.completed_at.desc(), Visit.id.desc()).first()
    return latest[0] if latest else None


def check_latest_visit_editable(db: Session, visit: Visit) -> None:
    latest_id = latest_customer_visit_id(db, visit.customer_id)
    if latest_id != visit.id:
        raise HTTPException(
            status_code=409,
            detail="This is an older customer visit and is read-only. Only the customer's latest visit can be edited.",
        )


def visible_customers_query(db: Session, user: dict):
    query = db.query(Customer)
    if user["role"] == "barber":
        # A barber's customer directory is limited to people they personally served.
        visit_customer_ids = db.query(Visit.customer_id).filter(
            Visit.barber_id == user["barber_id"]
        ).distinct()
        query = query.filter(Customer.id.in_(visit_customer_ids))
    return query


def customer_rows(db: Session, user: dict) -> list[dict]:
    visits_query = db.query(
        Visit.customer_id, func.count(Visit.id).label("visit_count"),
        func.max(Visit.completed_at).label("last_visit"),
    )
    if user["role"] == "barber":
        visits_query = visits_query.filter(Visit.barber_id == user["barber_id"])
    stats = visits_query.group_by(Visit.customer_id).all()
    stats_map = {row.customer_id: row for row in stats}
    result = []
    for c in visible_customers_query(db, user).order_by(Customer.name).all():
        row = stats_map.get(c.id)
        result.append({
            "id": c.id, "name": c.name, "phone": c.phone, "location": c.location or "",
            "messaging_consent": c.messaging_consent,
            "visit_count": int(row.visit_count) if row else 0,
            "last_visit": utc_iso(row.last_visit) if row else None,
        })
    return result


def branch_rows(db: Session, user: dict) -> list[dict]:
    query = db.query(Branch)
    if user["role"] == "barber":
        query = query.filter(Branch.id == branch_id_for_user(db, user))
    return [{"id": b.id, "name": b.name, "location": b.location}
            for b in query.order_by(Branch.name).all()]


def barber_rows(db: Session, user: dict) -> list[dict]:
    query = db.query(Barber)
    if user["role"] == "barber":
        query = query.filter(Barber.id == user["barber_id"])
    return [{"id": b.id, "name": b.name, "branch_id": b.branch_id}
            for b in query.order_by(Barber.name).all()]


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
    # Sequence numbers and edit eligibility are calculated across the full customer history,
    # not just the latest page of results or the currently signed-in barber's visible visits.
    history_rows = db.query(Visit.id, Visit.customer_id).order_by(
        Visit.completed_at.desc(), Visit.id.desc()
    ).all()
    customer_sequence: dict[int, dict[int, dict[str, int | bool]]] = {}
    per_customer: dict[int, list[int]] = {}
    for history_visit_id, customer_id in history_rows:
        per_customer.setdefault(customer_id, []).append(history_visit_id)
    for customer_id, ids in per_customer.items():
        total = len(ids)
        customer_sequence[customer_id] = {
            history_visit_id: {
                "visit_number": total - index,
                "visit_count": total,
                "is_latest_visit": index == 0,
            }
            for index, history_visit_id in enumerate(ids)
        }
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
        **customer_sequence.get(v.customer_id, {}).get(v.id, {
            "visit_number": 1, "visit_count": 1, "is_latest_visit": True,
        }),
        "can_edit": (
            customer_sequence.get(v.customer_id, {}).get(v.id, {}).get("is_latest_visit", False)
            and (user["role"] == "owner" or v.barber_id == user.get("barber_id"))
        ),
    } for v, c, b, barber, f, cr in rows]


def dashboard_data(db: Session, user: dict) -> dict:
    vq = db.query(Visit)
    fq = db.query(Feedback).join(Visit, Visit.id == Feedback.visit_id)
    tq = db.query(RecoveryTask).join(Feedback, Feedback.id == RecoveryTask.feedback_id).join(
        Visit, Visit.id == Feedback.visit_id
    )
    if user["role"] == "barber":
        vq = vq.filter(Visit.barber_id == user["barber_id"])
        fq = fq.filter(Visit.barber_id == user["barber_id"])
        tq = tq.filter(Visit.barber_id == user["barber_id"])
    visit_count = vq.count()
    revenue = float(vq.with_entities(func.coalesce(func.sum(Visit.amount), 0)).scalar() or 0)
    feedback_count, average, low_count = fq.with_entities(
        func.count(Feedback.id), func.avg(Feedback.rating),
        func.coalesce(func.sum(case((Feedback.rating <= 2, 1), else_=0)), 0)
    ).one()
    open_tasks = tq.filter(RecoveryTask.status != "resolved").count()
    customer_counts = vq.with_entities(Visit.customer_id, func.count(Visit.id).label("cnt")).group_by(Visit.customer_id).all()
    unique_count = len(customer_counts)
    repeat_count = sum(1 for row in customer_counts if row.cnt > 1)
    return {
        "total_visits": visit_count, "revenue": round(revenue, 2),
        "feedback_count": int(feedback_count), "low_feedback_count": int(low_count),
        "open_recovery_tasks": int(open_tasks),
        "average_rating": round(float(average), 1) if average is not None else None,
        "feedback_response_rate": round(feedback_count / visit_count * 100, 1) if visit_count else 0,
        "repeat_customer_rate": round(repeat_count / unique_count * 100, 1) if unique_count else 0,
        "branches": len(branch_rows(db, user)), "barbers": len(barber_rows(db, user)),
    }


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


def insight_data(db: Session, user: dict) -> dict:
    if user["role"] == "barber":
        row = db.query(
            Barber.id.label("barber_id"), Barber.name.label("barber_name"),
            Branch.name.label("branch_name"), func.count(Visit.id).label("visits"),
            func.coalesce(func.sum(Visit.amount), 0).label("revenue"),
            func.count(Feedback.id).label("feedback_count"), func.avg(Feedback.rating).label("average_rating"),
        ).join(Branch, Branch.id == Barber.branch_id).outerjoin(
            Visit, Visit.barber_id == Barber.id
        ).outerjoin(Feedback, Feedback.visit_id == Visit.id).filter(
            Barber.id == user["barber_id"]
        ).group_by(Barber.id, Barber.name, Branch.name).first()
        own = [] if not row else [{
            "barber_id": row.barber_id, "barber_name": row.barber_name, "branch_name": row.branch_name,
            "visits": int(row.visits), "revenue": round(float(row.revenue or 0), 2),
            "feedback_count": int(row.feedback_count),
            "average_rating": round(float(row.average_rating), 1) if row.average_rating is not None else None,
        }]
        return {"branches": [], "barbers": own}
    branch_q = db.query(
        Branch.id.label("branch_id"), Branch.name.label("branch_name"),
        func.count(Visit.id).label("visits"), func.coalesce(func.sum(Visit.amount), 0).label("revenue"),
        func.count(Feedback.id).label("feedback_count"), func.avg(Feedback.rating).label("average_rating"),
        func.coalesce(func.sum(case((Feedback.rating <= 2, 1), else_=0)), 0).label("low_rating_count"),
    ).outerjoin(Visit, Visit.branch_id == Branch.id).outerjoin(
        Feedback, Feedback.visit_id == Visit.id
    ).group_by(Branch.id, Branch.name).all()
    barber_q = db.query(
        Barber.id.label("barber_id"), Barber.name.label("barber_name"), Branch.name.label("branch_name"),
        func.count(Visit.id).label("visits"), func.coalesce(func.sum(Visit.amount), 0).label("revenue"),
        func.count(Feedback.id).label("feedback_count"), func.avg(Feedback.rating).label("average_rating"),
    ).join(Branch, Branch.id == Barber.branch_id).outerjoin(
        Visit, Visit.barber_id == Barber.id
    ).outerjoin(Feedback, Feedback.visit_id == Visit.id).group_by(
        Barber.id, Barber.name, Branch.name
    ).all()
    return {
        "branches": [{
            "branch_id": r.branch_id, "branch_name": r.branch_name, "visits": int(r.visits),
            "revenue": round(float(r.revenue or 0), 2), "feedback_count": int(r.feedback_count),
            "average_rating": round(float(r.average_rating), 1) if r.average_rating is not None else None,
            "low_rating_count": int(r.low_rating_count),
        } for r in branch_q],
        "barbers": [{
            "barber_id": r.barber_id, "barber_name": r.barber_name, "branch_name": r.branch_name,
            "visits": int(r.visits), "revenue": round(float(r.revenue or 0), 2),
            "feedback_count": int(r.feedback_count),
            "average_rating": round(float(r.average_rating), 1) if r.average_rating is not None else None,
        } for r in barber_q],
    }


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


def visit_snapshot(db: Session, visit: Visit) -> dict:
    return visit_json(db, visit)


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
