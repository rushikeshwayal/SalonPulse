"""Legacy /api management paths retained as compatibility adapters.

Canonical endpoints live in app.owner and app.barber. Business logic resides in
feature/common service modules; this file only preserves the older URL contract.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..common.bootstrap import build_bootstrap
from ..common.services.audit import list_audit_logs
from ..common.services.demo import reset
from ..common.services.feedback import create_feedback, list_feedback
from ..common.services.insights import get_insights
from ..common.services.messages import list_messages
from ..common.services.ratings import create_rating, list_ratings
from ..common.services.recovery import list_tasks, update_task
from ..common.services.staff import list_staff
from ..database import get_db
from ..dependencies import get_current_user, require_owner
from ..schemas import CustomerRatingCreate, FeedbackCreate, RecoveryUpdate

router = APIRouter()


@router.get("/api/feedback")
def get_feedback(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db),
                 user: dict = Depends(require_owner)):
    return list_feedback(db, user, limit)


@router.post("/api/feedback", status_code=201)
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db),
                    user: dict = Depends(require_owner)):
    return create_feedback(db, user, payload)


@router.get("/api/recovery-tasks")
def get_tasks(status: Optional[str] = None, limit: int = Query(default=20, ge=1, le=100),
              db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_tasks(db, user, status, limit)


@router.patch("/api/recovery-tasks/{task_id}")
def update_task_compat(task_id: int, payload: RecoveryUpdate, db: Session = Depends(get_db),
                       user: dict = Depends(require_owner)):
    return update_task(db, user, task_id, payload)


@router.get("/api/insights")
def get_insights_compat(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return get_insights(db, user)


@router.get("/api/messages")
def get_messages(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db),
                 user: dict = Depends(get_current_user)):
    return list_messages(db, user, limit)


@router.get("/api/audit-logs")
def get_audit_logs(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db),
                   user: dict = Depends(require_owner)):
    return list_audit_logs(db, user, limit)


@router.get("/api/customer-ratings")
def get_customer_ratings(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db),
                         user: dict = Depends(get_current_user)):
    return list_ratings(db, user, limit)


@router.post("/api/customer-ratings", status_code=201)
def create_customer_rating(payload: CustomerRatingCreate, db: Session = Depends(get_db),
                           user: dict = Depends(get_current_user)):
    return create_rating(db, user, payload)


@router.get("/api/staff-users")
def get_staff_users(db: Session = Depends(get_db), user: dict = Depends(require_owner)):
    return list_staff(db, user)


@router.post("/api/demo/reset")
def reset_demo(user: dict = Depends(require_owner), db: Session = Depends(get_db)):
    return reset(db, user)


@router.get("/api/bootstrap")
def bootstrap(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return build_bootstrap(db, user)
