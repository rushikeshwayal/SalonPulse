"""Customer interaction rating query and write operations."""

from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from ...models import Customer, CustomerRating, StaffUser, Visit
from ...schemas import CustomerRatingCreate
from ...services import add_audit, check_visit_access, utc_iso


def list_ratings(db: Session, user: dict, limit: int = 50) -> list[dict]:
    query = db.query(CustomerRating, Visit, Customer, StaffUser).join(
        Visit, Visit.id == CustomerRating.visit_id
    ).join(Customer, Customer.id == CustomerRating.customer_id).join(
        StaffUser, StaffUser.id == CustomerRating.barber_user_id)
    if user["role"] == "barber":
        query = query.filter(CustomerRating.barber_user_id == user["id"])
    rows = query.order_by(CustomerRating.created_at.desc()).limit(limit).all()
    return [{
        "id": rating.id, "visit_id": visit.id, "customer_id": customer.id,
        "customer_name": customer.name, "barber_username": staff.username,
        "rating": rating.rating, "note": rating.note, "created_at": utc_iso(rating.created_at),
    } for rating, visit, customer, staff in rows]


def create_rating(db: Session, user: dict, payload: CustomerRatingCreate) -> dict:
    if user["role"] != "barber":
        raise HTTPException(403, detail="Customer interaction ratings can only be recorded by the assigned barber.")
    visit = db.get(Visit, payload.visit_id)
    if not visit:
        raise HTTPException(404, detail="Visit not found.")
    check_visit_access(visit, user)
    rating = db.query(CustomerRating).filter_by(visit_id=visit.id).first()
    before = None if not rating else {"rating": rating.rating, "note": rating.note, "customer_id": rating.customer_id}
    action = "customer_rating.create"
    if rating:
        rating.rating, rating.note, rating.updated_at = payload.rating, payload.note.strip(), datetime.utcnow()
        action = "customer_rating.update"
    else:
        rating = CustomerRating(visit_id=visit.id, customer_id=visit.customer_id,
            barber_user_id=user["id"], rating=payload.rating, note=payload.note.strip())
        db.add(rating)
    db.flush()
    after = {"rating": rating.rating, "note": rating.note, "customer_id": rating.customer_id}
    add_audit(db, user, action, "customer_rating", rating.id or visit.id, before, after,
              "Visit-specific customer interaction note")
    db.commit()
    db.refresh(rating)
    return {"id": rating.id, "visit_id": rating.visit_id, "rating": rating.rating, "note": rating.note}
