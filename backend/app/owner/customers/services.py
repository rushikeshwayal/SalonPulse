"""Owner customer services over shared customer queries."""

from sqlalchemy.orm import Session
from ...common.services.customers import get_customer_review_history, list_customers, search_customers

def list_owner_customers(db: Session, user: dict): return list_customers(db, user)
def search_owner_customers(db: Session, user: dict, q: str): return search_customers(db, user, q)
def owner_customer_reviews(db: Session, user: dict, customer_id: int): return get_customer_review_history(db, user, customer_id)
