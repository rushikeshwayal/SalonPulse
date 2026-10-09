"""Barber home and initial personal workspace data."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_barber
from .schema import HomeSummary
from .services import get_bootstrap, get_home_summary

router = APIRouter(prefix="/api/barber", tags=["Barber / Home"], dependencies=[Depends(require_barber)])

@router.get("/home", response_model=HomeSummary, summary="Personal barber dashboard summary")
def barber_home(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_home_summary(db, user)

@router.get("/bootstrap", summary="Load all barber workspace data")
def barber_bootstrap(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_bootstrap(db, user)
