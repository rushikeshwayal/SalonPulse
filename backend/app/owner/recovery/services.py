"""Owner recovery task operations."""

from sqlalchemy.orm import Session
from ...schemas import RecoveryUpdate
from ...routers.management import get_tasks as _list, update_task as _update


def list_tasks(db: Session, user: dict, status: str | None, limit: int): return _list(status=status, limit=limit, db=db, user=user)
def update_task(db: Session, user: dict, task_id: int, payload: RecoveryUpdate): return _update(task_id=task_id, payload=payload, db=db, user=user)
