"""Management, reporting, recovery, audit and bootstrap endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import DATABASE_URL
from ..constants import SERVICE_CATALOG
from ..database import Base, SessionLocal, engine, get_db
from ..dependencies import get_current_user, require_owner
from ..models import (
    AuditLog, Barber, Branch, Customer, CustomerRating, Feedback, MessageLog,
    RecoveryTask, StaffUser, Visit, VisitService,
)
from ..schemas import CustomerRatingCreate, FeedbackCreate, RecoveryUpdate
from ..seed import seed
from ..services import (
    add_audit, audit_logs_initial, barber_rows, branch_rows, check_visit_access,
    customer_rows, dashboard_data, feedback_json, feedback_rows, insight_data,
    message_rows, task_json, task_rows, utc_iso, visit_rows, visit_snapshot,
)

router = APIRouter()


@router.get("/api/feedback")
def get_feedback(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db),
                 user: dict = Depends(require_owner)):
    return feedback_rows(db, user, limit)


@router.post("/api/feedback", status_code=201)
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db), user: dict = Depends(require_owner)):
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


@router.get("/api/recovery-tasks")
def get_tasks(status: Optional[str] = None, limit: int = Query(default=20, ge=1, le=100),
              db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    rows = task_rows(db, user, limit)
    if status:
        if status not in {"open", "in_progress", "resolved"}:
            raise HTTPException(400, detail="Invalid status.")
        rows = [r for r in rows if r["status"] == status]
    return rows


@router.patch("/api/recovery-tasks/{task_id}")
def update_task(task_id: int, payload: RecoveryUpdate, db: Session = Depends(get_db),
                user: dict = Depends(require_owner)):
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


@router.get("/api/insights")
def get_insights(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return insight_data(db, user)


@router.get("/api/messages")
def get_messages(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db),
                 user: dict = Depends(get_current_user)):
    return message_rows(db, user, limit)

@router.get("/api/audit-logs")
def get_audit_logs(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db),
                   user: dict = Depends(require_owner)):
    # Audit logs are management-only, not part of the barber-facing workspace.
    rows = db.query(AuditLog).order_by(
        AuditLog.created_at.desc(), AuditLog.id.desc()
    ).limit(limit).all()
    return [{
        "id": r.id, "actor_user_id": r.actor_user_id, "actor_username": r.actor_username,
        "actor_role": r.actor_role, "action": r.action, "entity_type": r.entity_type,
        "entity_id": r.entity_id, "before_data": r.before_data, "after_data": r.after_data,
        "change_note": r.change_note, "created_at": utc_iso(r.created_at),
    } for r in rows]


@router.get("/api/customer-ratings")
def get_customer_ratings(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db),
                         user: dict = Depends(get_current_user)):
    query = db.query(CustomerRating, Visit, Customer, StaffUser).join(
        Visit, Visit.id == CustomerRating.visit_id
    ).join(Customer, Customer.id == CustomerRating.customer_id).join(
        StaffUser, StaffUser.id == CustomerRating.barber_user_id)
    if user["role"] == "barber":
        query = query.filter(CustomerRating.barber_user_id == user["id"])
    rows = query.order_by(CustomerRating.created_at.desc()).limit(limit).all()
    return [{
        "id": r.id, "visit_id": v.id, "customer_id": c.id, "customer_name": c.name,
        "barber_username": staff.username, "rating": r.rating, "note": r.note,
        "created_at": utc_iso(r.created_at),
    } for r, v, c, staff in rows]


@router.post("/api/customer-ratings", status_code=201)
def create_customer_rating(payload: CustomerRatingCreate, db: Session = Depends(get_db),
                           user: dict = Depends(get_current_user)):
    if user["role"] != "barber":
        raise HTTPException(403, detail="Customer interaction ratings can only be recorded by the assigned barber.")
    visit = db.get(Visit, payload.visit_id)
    if not visit:
        raise HTTPException(404, detail="Visit not found.")
    check_visit_access(visit, user)
    rating = db.query(CustomerRating).filter_by(visit_id=visit.id).first()
    before = None if not rating else {"rating": rating.rating, "note": rating.note, "customer_id": rating.customer_id}
    action = "customer_rating.create"
    if rating:
        rating.rating, rating.note, rating.updated_at = payload.rating, payload.note.strip(), datetime.utcnow()
        action = "customer_rating.update"
    else:
        rating = CustomerRating(visit_id=visit.id, customer_id=visit.customer_id,
            barber_user_id=user["id"], rating=payload.rating, note=payload.note.strip())
        db.add(rating)
    db.flush()
    after = {"rating": rating.rating, "note": rating.note, "customer_id": rating.customer_id}
    add_audit(db, user, action, "customer_rating", rating.id or visit.id, before, after,
              "Visit-specific customer interaction note")
    db.commit()
    db.refresh(rating)
    return {"id": rating.id, "visit_id": rating.visit_id, "rating": rating.rating, "note": rating.note}


@router.get("/api/staff-users")
def get_staff_users(db: Session = Depends(get_db), user: dict = Depends(require_owner)):
    staff_rows = db.query(StaffUser).order_by(StaffUser.role, StaffUser.display_name).all()
    barbers = {b.id: b for b in db.query(Barber).all()}
    branches = {b.id: b for b in db.query(Branch).all()}
    return [{
        "id": staff.id, "username": staff.username, "email": staff.email,
        "display_name": staff.display_name, "role": staff.role, "barber_id": staff.barber_id,
        "branch_name": branches.get(barbers[staff.barber_id].branch_id).name
            if staff.barber_id in barbers and barbers[staff.barber_id].branch_id in branches else "",
        "is_active": staff.is_active, "must_change_password": staff.must_change_password,
    } for staff in staff_rows]


@router.post("/api/demo/reset")
def reset_demo(user: dict = Depends(require_owner), db: Session = Depends(get_db)):
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


@router.get("/api/bootstrap")
def bootstrap(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return {
        "user": user, "dashboard": dashboard_data(db, user),
        "branches": branch_rows(db, user), "barbers": barber_rows(db, user),
        "customers": customer_rows(db, user), "visits": visit_rows(db, user, 20),
        "feedback": feedback_rows(db, user, 20) if user["role"] == "owner" else [],
        "tasks": task_rows(db, user, 20) if user["role"] == "owner" else [],
        "insights": insight_data(db, user),
        "messages": message_rows(db, user, 10) if user["role"] == "owner" else [],
        "serviceCatalog": SERVICE_CATALOG,
        "auditLogs": audit_logs_initial(db, user) if user["role"] == "owner" else [],
    }
