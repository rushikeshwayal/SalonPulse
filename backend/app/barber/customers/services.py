"""Barber customer services over the shared, access-scoped customer queries."""

from sqlalchemy.orm import Session
from ...common.services.customers import (
    get_customer_review_history as _get_customer_review_history,
    list_customers as _list_customers,
    search_customers as _search_customers,
)


def list_customers(db: Session, user: dict):
    return _list_customers(db, user)

def search_customers(db: Session, user: dict, q: str):
    return _search_customers(db, user, q)

def customer_reviews(db: Session, user: dict, customer_id: int):
    return _get_customer_review_history(db, user, customer_id)
