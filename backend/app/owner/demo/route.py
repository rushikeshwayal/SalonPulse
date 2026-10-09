"""Owner-only local demo tools; disabled for production PostgreSQL."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from .services import reset

router = APIRouter(prefix="/api/owner/demo", tags=["Owner / Demo Tools"], dependencies=[Depends(require_owner)])

@router.post("/reset", summary="Reset local fictional demo data")
def reset_demo(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return reset(db, user)
