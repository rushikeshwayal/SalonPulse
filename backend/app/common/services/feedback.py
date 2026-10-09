"""Owner feedback management service."""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from ...models import Feedback, RecoveryTask, Visit
from ...schemas import FeedbackCreate
from ...services import check_visit_access, feedback_json, feedback_rows


def list_feedback(db: Session, user: dict, limit: int = 20) -> list[dict]:
    return feedback_rows(db, user, limit)


def create_feedback(db: Session, user: dict, payload: FeedbackCreate) -> dict:
    visit = db.get(Visit, payload.visit_id)
    if not visit:
        raise HTTPException(404, detail="Visit not found.")
    check_visit_access(visit, user)
    if db.query(Feedback).filter_by(visit_id=visit.id).first():
        raise HTTPException(409, detail="Feedback already exists for this visit.")
    feedback = Feedback(visit_id=visit.id, rating=payload.rating, comment=payload.comment.strip())
    db.add(feedback)
    db.flush()
    if payload.rating <= 2:
        db.add(RecoveryTask(feedback_id=feedback.id, status="open"))
    db.commit()
    db.refresh(feedback)
    return {"feedback": feedback_json(db, feedback), "recovery_created": payload.rating <= 2}
