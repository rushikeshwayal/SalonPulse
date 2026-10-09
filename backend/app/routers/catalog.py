"""Branch, barber and service-catalog endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..constants import SERVICE_CATALOG
from ..database import get_db
from ..dependencies import get_current_user
from ..services import barber_rows, branch_rows

router = APIRouter()


@router.get("/api/service-catalog")
def get_service_catalog(user: dict = Depends(get_current_user)):
    return SERVICE_CATALOG


@router.get("/api/branches")
def get_branches(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return branch_rows(db, user)


@router.get("/api/barbers")
def get_barbers(branch_id: Optional[int] = None, db: Session = Depends(get_db),
                user: dict = Depends(get_current_user)):
    rows = barber_rows(db, user)
    return [b for b in rows if not branch_id or b["branch_id"] == branch_id]
