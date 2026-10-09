"""Owner recovery queue and resolution endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import get_current_user, require_owner
from ...schemas import RecoveryUpdate
from .services import list_tasks, update_task

router = APIRouter(prefix="/api/owner/recovery-tasks", tags=["Owner / Recovery"], dependencies=[Depends(require_owner)])

@router.get("", summary="List follow-up and recovery tasks")
def tasks(status: str | None = None, limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_tasks(db, user, status, limit)

@router.patch("/{task_id}", summary="Update the status of a recovery task")
def update(task_id: int, payload: RecoveryUpdate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return update_task(db, user, task_id, payload)
