"""Owner customer list, search and feedback history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from .schema import CustomerReviewHistory
from .services import customer_reviews, list_customers, search_customers

router = APIRouter(prefix="/api/owner/customers", tags=["Owner / Customers"], dependencies=[Depends(require_owner)])

@router.get("", summary="List customers")
def customers(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_customers(db, user)

@router.get("/search", summary="Search customers by name or phone")
def search(q: str = Query(min_length=1, max_length=120), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return search_customers(db, user, q)

@router.get("/{customer_id}/reviews", response_model=CustomerReviewHistory, summary="Customer reviews from recorded visits")
def reviews(customer_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return customer_reviews(db, user, customer_id)
