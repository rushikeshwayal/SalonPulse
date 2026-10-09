"""Owner home and initial workspace data endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_user, require_owner
from .schema import HomeSummary
from .services import get_bootstrap, get_home_summary

router = APIRouter(prefix="/api/owner", tags=["Owner / Home"], dependencies=[Depends(require_owner)])


@router.get("/home", response_model=HomeSummary, summary="Owner dashboard summary")
def owner_home(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_home_summary(db, user)


@router.get("/bootstrap", summary="Load all owner workspace data")
def owner_bootstrap(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_bootstrap(db, user)
