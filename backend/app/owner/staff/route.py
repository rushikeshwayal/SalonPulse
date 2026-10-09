"""Owner-only staff accounts and assignment listing."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from .services import list_staff

router = APIRouter(prefix="/api/owner/staff-users", tags=["Owner / Staff"], dependencies=[Depends(require_owner)])

@router.get("", summary="List staff accounts and their branch assignments")
def staff(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_staff(db, user)
