"""Barber interaction rating view and create/update workflow."""

from sqlalchemy.orm import Session
from ...schemas import CustomerRatingCreate
from ...common.services.ratings import create_rating as _create_rating, list_ratings as _list_ratings


def list_ratings(db: Session, user: dict, limit: int = 50):
    return _list_ratings(db, user, limit)

def create_rating(db: Session, user: dict, payload: CustomerRatingCreate):
    return _create_rating(db, user, payload)
