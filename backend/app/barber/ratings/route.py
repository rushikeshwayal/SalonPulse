"""Barber interaction rating endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_barber
from ...schemas import CustomerRatingCreate
from .services import create_rating, list_ratings

router = APIRouter(prefix="/api/barber/customer-ratings", tags=["Barber / Customer Ratings"], dependencies=[Depends(require_barber)])

@router.get("", summary="List this barber's customer interaction ratings")
def ratings(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_ratings(db, user, limit)

@router.post("", status_code=201, summary="Record a customer interaction rating for a visit")
def create(payload: CustomerRatingCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return create_rating(db, user, payload)
