"""Dashboard and owner/barber performance aggregate projections."""

from __future__ import annotations

from sqlalchemy import case, func
from sqlalchemy.orm import Session
from ..models import Barber, Branch, Feedback, RecoveryTask, Visit
from .catalog import barber_rows, branch_rows

def dashboard_data(db: Session, user: dict) -> dict:
    vq = db.query(Visit)
    fq = db.query(Feedback).join(Visit, Visit.id == Feedback.visit_id)
    tq = db.query(RecoveryTask).join(Feedback, Feedback.id == RecoveryTask.feedback_id).join(
        Visit, Visit.id == Feedback.visit_id
    )
    if user["role"] == "barber":
        vq = vq.filter(Visit.barber_id == user["barber_id"])
        fq = fq.filter(Visit.barber_id == user["barber_id"])
        tq = tq.filter(Visit.barber_id == user["barber_id"])
    visit_count = vq.count()
    revenue = float(vq.with_entities(func.coalesce(func.sum(Visit.amount), 0)).scalar() or 0)
    feedback_count, average, low_count = fq.with_entities(
        func.count(Feedback.id), func.avg(Feedback.rating),
        func.coalesce(func.sum(case((Feedback.rating <= 2, 1), else_=0)), 0)
    ).one()
    open_tasks = tq.filter(RecoveryTask.status != "resolved").count()
    customer_counts = vq.with_entities(Visit.customer_id, func.count(Visit.id).label("cnt")).group_by(Visit.customer_id).all()
    unique_count = len(customer_counts)
    repeat_count = sum(1 for row in customer_counts if row.cnt > 1)
    return {
        "total_visits": visit_count, "revenue": round(revenue, 2),
        "feedback_count": int(feedback_count), "low_feedback_count": int(low_count),
        "open_recovery_tasks": int(open_tasks),
        "average_rating": round(float(average), 1) if average is not None else None,
        "feedback_response_rate": round(feedback_count / visit_count * 100, 1) if visit_count else 0,
        "repeat_customer_rate": round(repeat_count / unique_count * 100, 1) if unique_count else 0,
        "branches": len(branch_rows(db, user)), "barbers": len(barber_rows(db, user)),
    }

def insight_data(db: Session, user: dict) -> dict:
    if user["role"] == "barber":
        row = db.query(
            Barber.id.label("barber_id"), Barber.name.label("barber_name"),
            Branch.name.label("branch_name"), func.count(Visit.id).label("visits"),
            func.coalesce(func.sum(Visit.amount), 0).label("revenue"),
            func.count(Feedback.id).label("feedback_count"), func.avg(Feedback.rating).label("average_rating"),
        ).join(Branch, Branch.id == Barber.branch_id).outerjoin(
            Visit, Visit.barber_id == Barber.id
        ).outerjoin(Feedback, Feedback.visit_id == Visit.id).filter(
            Barber.id == user["barber_id"]
        ).group_by(Barber.id, Barber.name, Branch.name).first()
        own = [] if not row else [{
            "barber_id": row.barber_id, "barber_name": row.barber_name, "branch_name": row.branch_name,
            "visits": int(row.visits), "revenue": round(float(row.revenue or 0), 2),
            "feedback_count": int(row.feedback_count),
            "average_rating": round(float(row.average_rating), 1) if row.average_rating is not None else None,
        }]
        return {"branches": [], "barbers": own}
    branch_q = db.query(
        Branch.id.label("branch_id"), Branch.name.label("branch_name"),
        func.count(Visit.id).label("visits"), func.coalesce(func.sum(Visit.amount), 0).label("revenue"),
        func.count(Feedback.id).label("feedback_count"), func.avg(Feedback.rating).label("average_rating"),
        func.coalesce(func.sum(case((Feedback.rating <= 2, 1), else_=0)), 0).label("low_rating_count"),
    ).outerjoin(Visit, Visit.branch_id == Branch.id).outerjoin(
        Feedback, Feedback.visit_id == Visit.id
    ).group_by(Branch.id, Branch.name).all()
    barber_q = db.query(
        Barber.id.label("barber_id"), Barber.name.label("barber_name"), Branch.name.label("branch_name"),
        func.count(Visit.id).label("visits"), func.coalesce(func.sum(Visit.amount), 0).label("revenue"),
        func.count(Feedback.id).label("feedback_count"), func.avg(Feedback.rating).label("average_rating"),
    ).join(Branch, Branch.id == Barber.branch_id).outerjoin(
        Visit, Visit.barber_id == Barber.id
    ).outerjoin(Feedback, Feedback.visit_id == Visit.id).group_by(
        Barber.id, Barber.name, Branch.name
    ).all()
    return {
        "branches": [{
            "branch_id": r.branch_id, "branch_name": r.branch_name, "visits": int(r.visits),
            "revenue": round(float(r.revenue or 0), 2), "feedback_count": int(r.feedback_count),
            "average_rating": round(float(r.average_rating), 1) if r.average_rating is not None else None,
            "low_rating_count": int(r.low_rating_count),
        } for r in branch_q],
        "barbers": [{
            "barber_id": r.barber_id, "barber_name": r.barber_name, "branch_name": r.branch_name,
            "visits": int(r.visits), "revenue": round(float(r.revenue or 0), 2),
            "feedback_count": int(r.feedback_count),
            "average_rating": round(float(r.average_rating), 1) if r.average_rating is not None else None,
        } for r in barber_q],
    }
