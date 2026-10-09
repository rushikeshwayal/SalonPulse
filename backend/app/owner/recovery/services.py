"""Owner recovery queue operations."""

from sqlalchemy.orm import Session
from ...schemas import RecoveryUpdate
from ...common.services.recovery import list_tasks, update_task

def list_owner_tasks(db: Session, user: dict, status: str | None, limit: int): return list_tasks(db, user, status, limit)
def update_owner_task(db: Session, user: dict, task_id: int, payload: RecoveryUpdate): return update_task(db, user, task_id, payload)

def list_tasks(db: Session, user: dict, status: str | None = None, limit: int = 20): return list_owner_tasks(db, user, status, limit)
def update_task(db: Session, user: dict, task_id: int, payload: RecoveryUpdate): return update_owner_task(db, user, task_id, payload)
