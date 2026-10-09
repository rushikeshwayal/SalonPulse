"""Owner-only financial reporting endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_user, require_owner
from .schema import FinanceOverview
from .services import finance_overview

router = APIRouter(prefix="/api/owner/finance", tags=["Owner / Finance"], dependencies=[Depends(require_owner)])


@router.get("", response_model=FinanceOverview, summary="Revenue totals and performance by branch/barber")
def get_finance_overview(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return finance_overview(db, user)
