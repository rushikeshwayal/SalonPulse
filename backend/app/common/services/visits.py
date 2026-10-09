"""Shared visit use-cases used by owner, barber and legacy routes."""

from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from ...models import AuditLog, Barber, Branch, Customer, MessageLog, Visit, VisitService
from ...schemas import VisitCreate, VisitServiceInput, VisitUpdate
from ...services import (
    add_audit, branch_id_for_user, check_latest_visit_editable, check_visit_access,
    dashboard_data, message_for, normalize_phone, utc_iso, visit_rows, visit_snapshot,
)


def get_dashboard(db: Session, user: dict) -> dict:
    return dashboard_data(db, user)


def list_visits(db: Session, user: dict, limit: int = 20) -> list[dict]:
    return visit_rows(db, user, limit)


def get_visit_history(db: Session, user: dict, visit_id: int) -> list[dict]:
    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, detail="Visit not found.")
    check_visit_access(visit, user)
    rows = db.query(AuditLog).filter_by(entity_type="visit", entity_id=visit_id).order_by(
        AuditLog.created_at.desc(), AuditLog.id.desc()
    ).limit(100).all()
    return [{
        "id": r.id, "actor_username": r.actor_username, "actor_role": r.actor_role,
        "action": r.action, "before_data": r.before_data, "after_data": r.after_data,
        "change_note": r.change_note, "created_at": utc_iso(r.created_at),
    } for r in rows]


def update_visit(db: Session, user: dict, visit_id: int, payload: VisitUpdate) -> dict:
    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, detail="Visit not found.")
    check_visit_access(visit, user)
    check_latest_visit_editable(db, visit)
    before = visit_snapshot(db, visit)
    if payload.customer_id is not None:
        if payload.customer_id != visit.customer_id:
            raise HTTPException(
                status_code=400,
                detail="A visit cannot be reassigned to another customer during editing. Create a new visit for a different customer.",
            )
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(404, detail="Customer not found.")
        if user["role"] == "barber":
            ids = {x[0] for x in db.query(Visit.customer_id).filter(
                Visit.branch_id == branch_id_for_user(db, user)
            ).distinct().all()}
            if customer.id not in ids:
                raise HTTPException(403, detail="Customer is not in your branch's records.")
        visit.customer_id = customer.id
    if user["role"] == "owner":
        if payload.branch_id is not None:
            if not db.get(Branch, payload.branch_id):
                raise HTTPException(404, detail="Branch not found.")
            visit.branch_id = payload.branch_id
        if payload.barber_id is not None:
            barber = db.get(Barber, payload.barber_id)
            if not barber:
                raise HTTPException(404, detail="Barber not found.")
            if barber.branch_id != visit.branch_id:
                raise HTTPException(400, detail="Selected barber must belong to the visit branch.")
            visit.barber_id = barber.id
    elif payload.branch_id is not None and payload.branch_id != visit.branch_id:
        raise HTTPException(403, detail="Barbers cannot move visits between branches.")
    if payload.completed_at is not None:
        stamp = payload.completed_at
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        visit.completed_at = stamp.astimezone(timezone.utc).replace(tzinfo=None)
    if payload.messaging_consent is not None:
        visit.feedback_requested = payload.messaging_consent
    if payload.services is not None:
        if not payload.services:
            raise HTTPException(400, detail="A visit must contain at least one service.")
        visit.service_name = " + ".join(
            f"{line.service_name} ×{line.quantity}" if line.quantity > 1 else line.service_name
            for line in payload.services
        )
        visit.amount = round(sum(line.quantity * line.unit_price for line in payload.services), 2)
        db.query(VisitService).filter_by(visit_id=visit.id).delete(synchronize_session=False)
        db.flush()
        for line in payload.services:
            db.add(VisitService(
                visit_id=visit.id, service_name=line.service_name, quantity=line.quantity,
                unit_price=line.unit_price, line_total=round(line.quantity * line.unit_price, 2),
            ))
    visit.updated_by_user_id = user["id"]
    db.flush()
    after = visit_snapshot(db, visit)
    add_audit(db, user, "visit.update", "visit", visit.id, before, after, payload.change_note)
    db.commit()
    db.refresh(visit)
    return {"visit": visit_snapshot(db, visit)}


def create_visit(db: Session, user: dict, payload: VisitCreate) -> dict:
    if user["role"] == "barber":
        assigned = db.get(Barber, user["barber_id"])
        if not assigned:
            raise HTTPException(403, detail="This account is not assigned to a barber.")
        if payload.branch_id != assigned.branch_id:
            raise HTTPException(403, detail="You can only record visits at your assigned branch.")
        branch_id, barber_id = assigned.branch_id, assigned.id
    else:
        branch_id, barber_id = payload.branch_id, payload.barber_id
    branch, barber = db.get(Branch, branch_id), db.get(Barber, barber_id)
    if not branch or not barber:
        raise HTTPException(404, detail="Branch or barber not found.")
    if barber.branch_id != branch.id:
        raise HTTPException(400, detail="Barber does not belong to the selected branch.")
    if payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(404, detail="Customer not found. Search again and select a customer.")
        if user["role"] == "barber":
            # Returning-customer lookup is private to visits assigned to the signed-in barber.
            ids = {x[0] for x in db.query(Visit.customer_id).filter(
                Visit.barber_id == user["barber_id"]
            ).distinct().all()}
            if customer.id not in ids:
                raise HTTPException(403, detail="You can only select customers from your own visit history.")
    else:
        name, phone, location = (payload.customer_name or "").strip(), (payload.customer_phone or "").strip(), (payload.customer_location or "").strip()
        normalized_phone = normalize_phone(phone)
        if len(normalized_phone) < 7 or len(normalized_phone) > 15:
            raise HTTPException(400, detail="Enter a valid customer phone number (7–15 digits).")
        if not name:
            raise HTTPException(400, detail="Customer name is required for a new customer.")
        for existing in db.query(Customer).all():
            if normalize_phone(existing.phone) and normalize_phone(existing.phone) == normalized_phone:
                raise HTTPException(409, detail="This phone number is already registered. Search for the existing customer.")
        customer = Customer(name=name, phone=phone, location=location, created_by_user_id=user["id"])
        db.add(customer)
        db.flush()
    lines = payload.services or (
        [VisitServiceInput(service_name=payload.service_name, quantity=1, unit_price=payload.amount)]
        if payload.service_name and payload.amount is not None else []
    )
    if not lines:
        raise HTTPException(400, detail="Add at least one service.")
    amount = round(sum(line.quantity * line.unit_price for line in lines), 2)
    summary = " + ".join(f"{line.service_name} ×{line.quantity}" if line.quantity > 1 else line.service_name for line in lines)
    if payload.messaging_consent:
        customer.messaging_consent = True
    stamp = payload.completed_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc).replace(tzinfo=None)
    visit = Visit(
        customer_id=customer.id, branch_id=branch.id, barber_id=barber.id, service_name=summary,
        amount=amount, completed_at=stamp, feedback_requested=payload.messaging_consent,
        created_by_user_id=user["id"], updated_by_user_id=user["id"],
    )
    db.add(visit)
    db.flush()
    for line in lines:
        db.add(VisitService(visit_id=visit.id, service_name=line.service_name,
            quantity=line.quantity, unit_price=line.unit_price,
            line_total=round(line.quantity * line.unit_price, 2)))
    if payload.messaging_consent:
        db.add(MessageLog(visit_id=visit.id, status="mock_queued", message=message_for(customer.name)))
    db.flush()
    add_audit(db, user, "visit.create", "visit", visit.id, None, visit_snapshot(db, visit), "Visit created")
    db.commit()
    db.refresh(visit)
    return {"visit": visit_snapshot(db, visit),
            "message_status": "mock_queued" if payload.messaging_consent else "not_requested",
            "notice": "Demo only: no real WhatsApp message was sent."}
