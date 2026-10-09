"""Legacy customer API paths retained as compatibility adapters."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..common.services.customers import get_customer_review_history, list_customers, search_customers
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter()

@router.get("/api/customers/search")
def search_customers_compat(q: str = Query(min_length=1, max_length=120), db: Session = Depends(get_db),
                            user: dict = Depends(get_current_user)):
    return search_customers(db, user, q)

@router.get("/api/customers")
def get_customers_compat(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_customers(db, user)

@router.get("/api/customers/{customer_id}/reviews")
def reviews_compat(customer_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_customer_review_history(db, user, customer_id)
