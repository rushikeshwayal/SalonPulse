"""Shared authorization-aware domain checks and customer visibility query."""

from __future__ import annotations

from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from ..models import Barber, Customer, Visit

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
