"""Barber reference-data routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...common.projections.catalog import barber_rows, branch_rows
from ...constants import SERVICE_CATALOG
from ...database import get_db
from ...dependencies import get_current_user, require_barber

router = APIRouter(
    prefix="/api/barber/catalog",
    tags=["Barber / Reference Data"],
    dependencies=[Depends(require_barber)],
)


@router.get("/branches", summary="List branches")
def branches(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return branch_rows(db, user)


@router.get("/barbers", summary="List barbers")
def barbers(
    branch_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    rows = barber_rows(db, user)
    if branch_id is not None:
        rows = [barber for barber in rows if barber["branch_id"] == branch_id]
    return rows


@router.get("/services", summary="Service catalogue")
def services():
    return SERVICE_CATALOG
