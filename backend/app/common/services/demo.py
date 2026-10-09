"""Owner-only demo reset; persistent production database reset is intentionally blocked."""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from ...config import DATABASE_URL
from ...models import Customer, CustomerRating, Feedback, MessageLog, RecoveryTask, Visit, VisitService
from ...seed import seed


def reset(db: Session, user: dict) -> dict:
    if not DATABASE_URL.startswith("sqlite:"):
        raise HTTPException(
            status_code=403,
            detail="Demo reset is disabled for the persistent production database to protect customer records.",
        )
    for model in (CustomerRating, MessageLog, RecoveryTask, Feedback, VisitService, Visit, Customer):
        db.query(model).delete(synchronize_session=False)
    db.commit()
    seed(db, reset=False)
    return {"status": "ok", "message": "Local demo activity reset; audit history was preserved."}
