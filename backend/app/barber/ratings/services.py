"""Barber customer-interaction rating operations."""

from sqlalchemy.orm import Session
from ...schemas import CustomerRatingCreate
from ...routers.management import get_customer_ratings as _list, create_customer_rating as _create

def list_ratings(db: Session, user: dict, limit: int = 50): return _list(limit=limit, db=db, user=user)
def create_rating(db: Session, user: dict, payload: CustomerRatingCreate): return _create(payload=payload, db=db, user=user)
