"""Branch and barber list projections for workspaces."""

from __future__ import annotations

from sqlalchemy.orm import Session
from ..models import Barber, Branch
from .access import branch_id_for_user

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
