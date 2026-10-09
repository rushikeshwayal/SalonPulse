"""Barber reference-data routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_barber
from .services import list_barbers, list_branches, list_services

router = APIRouter(prefix="/api/barber/catalog", tags=["Barber / Reference Data"], dependencies=[Depends(require_barber)])

@router.get("/branches", summary="List branches")
def branches(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_branches(db, user)

@router.get("/barbers", summary="List barbers")
def barbers(branch_id: int | None = Query(default=None), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_barbers(db, user, branch_id)

@router.get("/services", summary="Service catalogue")
def services():
    return list_services()
