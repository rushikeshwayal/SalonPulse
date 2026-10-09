"""Barber interaction rating view and create/update workflow."""

from sqlalchemy.orm import Session
from ...schemas import CustomerRatingCreate
from ...common.services.ratings import create_rating, list_ratings

def list_barber_ratings(db: Session, user: dict, limit: int = 50): return list_ratings(db, user, limit)
def create_barber_rating(db: Session, user: dict, payload: CustomerRatingCreate): return create_rating(db, user, payload)

def list_ratings(db: Session, user: dict, limit: int = 50): return list_barber_ratings(db, user, limit)
def create_rating(db: Session, user: dict, payload: CustomerRatingCreate): return create_barber_rating(db, user, payload)
