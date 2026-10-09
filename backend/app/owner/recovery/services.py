"""Owner recovery queue operations."""

from sqlalchemy.orm import Session
from ...schemas import RecoveryUpdate
from ...common.services.recovery import list_tasks as _list_tasks, update_task as _update_task


def list_tasks(db: Session, user: dict, status: str | None, limit: int):
    return _list_tasks(db, user, status, limit)

def update_task(db: Session, user: dict, task_id: int, payload: RecoveryUpdate):
    return _update_task(db, user, task_id, payload)
