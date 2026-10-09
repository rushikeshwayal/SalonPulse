"""Customer directory, search and review-history endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Barber, Branch, Customer, Feedback, Visit
from ..services import customer_rows, normalize_phone, utc_iso

router = APIRouter()


@router.get("/api/customers/search")
def search_customers(q: str = Query(min_length=1, max_length=120), db: Session = Depends(get_db),
                     user: dict = Depends(get_current_user)):
    term, digits = q.strip(), normalize_phone(q.strip())
    matches = []
    for customer in customer_rows(db, user):
        name_match = term.casefold() in customer["name"].casefold()
        phone_digits = normalize_phone(customer["phone"])
        phone_match = bool(digits) and (phone_digits == digits or (len(digits) >= 3 and digits in phone_digits))
        if name_match or phone_match:
            matches.append(customer)
    if digits:
        matches.sort(key=lambda c: normalize_phone(c["phone"]) != digits)
    return matches[:10]


@router.get("/api/customers")
def get_customers(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return customer_rows(db, user)


@router.get("/api/customers/{customer_id}/reviews")
def get_customer_review_history(customer_id: int, db: Session = Depends(get_db),
                                user: dict = Depends(get_current_user)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    query = db.query(Visit, Branch, Barber, Feedback).join(
        Branch, Branch.id == Visit.branch_id
    ).join(Barber, Barber.id == Visit.barber_id).outerjoin(
        Feedback, Feedback.visit_id == Visit.id
    ).filter(Visit.customer_id == customer_id)
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(Visit.completed_at.desc(), Visit.id.desc()).all()
    # Do not reveal a customer record to a barber unless they have served that customer.
    if user["role"] == "barber" and not rows:
        raise HTTPException(status_code=404, detail="Customer not found in your visit history.")

    visit_count = len(rows)
    reviews = []
    for index, (visit, branch, barber, feedback) in enumerate(rows):
        if not feedback:
            continue
        reviews.append({
            "id": feedback.id,
            "visit_id": visit.id,
            "visit_number": visit_count - index,
            "completed_at": utc_iso(visit.completed_at),
            "service_name": visit.service_name,
            "amount": visit.amount,
            "branch_name": branch.name,
            "barber_name": barber.name,
            "rating": feedback.rating,
            "comment": feedback.comment or "",
            "created_at": utc_iso(feedback.created_at),
        })

    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone or "",
            "location": customer.location or "",
        },
        "visit_count": visit_count,
        "review_count": len(reviews),
        "reviews": reviews,
    }
