"""Recovery queue query and update business operations."""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from ...models import RecoveryTask
from ...schemas import RecoveryUpdate
from ...services import add_audit, task_json, task_rows


def list_tasks(db: Session, user: dict, status: str | None = None, limit: int = 20) -> list[dict]:
    rows = task_rows(db, user, limit)
    if status:
        if status not in {"open", "in_progress", "resolved"}:
            raise HTTPException(400, detail="Invalid status.")
        rows = [row for row in rows if row["status"] == status]
    return rows


def update_task(db: Session, user: dict, task_id: int, payload: RecoveryUpdate) -> dict:
    task = db.get(RecoveryTask, task_id)
    if not task:
        raise HTTPException(404, detail="Recovery task not found.")
    before = task_json(db, task)
    task.status, task.resolution_note = payload.status, payload.resolution_note.strip()
    db.flush()
    add_audit(db, user, "recovery_task.update", "recovery_task", task.id, before,
              task_json(db, task), payload.resolution_note[:500])
    db.commit()
    db.refresh(task)
    return task_json(db, task)
