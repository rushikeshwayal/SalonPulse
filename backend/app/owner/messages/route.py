"""Owner-only outbound message activity (mock mode)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from .services import list_messages

router = APIRouter(prefix="/api/owner/messages", tags=["Owner / Messaging"], dependencies=[Depends(require_owner)])

@router.get("", summary="List mock message delivery attempts")
def messages(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_messages(db, user, limit)
