from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT.parent / "frontend"
DB = ROOT / "salonpulse.db"
engine = create_engine(f"sqlite:///{DB}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(120))


class Barber(Base):
    __tablename__ = "barbers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    name: Mapped[str] = mapped_column(String(120))


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40), default="")
    messaging_consent: Mapped[bool] = mapped_column(Boolean, default=False)


class Visit(Base):
    __tablename__ = "visits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    barber_id: Mapped[int] = mapped_column(ForeignKey("barbers.id"))
    service_name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[float] = mapped_column(Float)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    feedback_requested: Mapped[bool] = mapped_column(Boolean, default=False)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), unique=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RecoveryTask(Base):
    __tablename__ = "recovery_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id"))
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MessageLog(Base):
    __tablename__ = "message_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"))
    status: Mapped[str] = mapped_column(String(40), default="mock_queued")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VisitCreate(BaseModel):
    customer_id: int
    branch_id: int
    barber_id: int
    service_name: str = Field(min_length=2, max_length=120)
    amount: float = Field(ge=0, le=100000)
    messaging_consent: bool = False


class FeedbackCreate(BaseModel):
    visit_id: int
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class RecoveryUpdate(BaseModel):
    status: str = Field(pattern="^(open|in_progress|resolved)$")
    resolution_note: str = Field(default="", max_length=2000)


app = FastAPI(
    title="SalonPulse API",
    version="0.1.0",
    description="Salon feedback and service recovery demo. Messaging is mock-only.",
)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def message_for(name: str) -> str:
    first = (name or "there").split()[0]
    return (
        f"Hi {first}, thanks for visiting us today. We'd appreciate your honest feedback "
        "about your experience. Your feedback is shared with salon management so we can improve. "
        "Reply with a rating from 1 to 5. You can opt out of future messages at any time."
    )


def visit_json(db: Session, v: Visit) -> dict:
    c, b, barber = db.get(Customer, v.customer_id), db.get(Branch, v.branch_id), db.get(Barber, v.barber_id)
    f = db.query(Feedback).filter_by(visit_id=v.id).first()
    return {
        "id": v.id, "customer_id": v.customer_id, "customer_name": c.name if c else "Unknown",
        "branch_id": v.branch_id, "branch_name": b.name if b else "Unknown",
        "barber_id": v.barber_id, "barber_name": barber.name if barber else "Unknown",
        "service_name": v.service_name, "amount": v.amount,
        "completed_at": v.completed_at.isoformat(), "feedback_requested": v.feedback_requested,
        "feedback_received": bool(f), "rating": f.rating if f else None,
    }


def feedback_json(db: Session, f: Feedback) -> dict:
    v = db.get(Visit, f.visit_id)
    c = db.get(Customer, v.customer_id) if v else None
    b = db.get(Branch, v.branch_id) if v else None
    barber = db.get(Barber, v.barber_id) if v else None
    task = db.query(RecoveryTask).filter_by(feedback_id=f.id).first()
    return {
        "id": f.id, "visit_id": f.visit_id, "customer_name": c.name if c else "Unknown",
        "branch_name": b.name if b else "Unknown", "barber_name": barber.name if barber else "Unknown",
        "rating": f.rating, "comment": f.comment, "created_at": f.created_at.isoformat(),
        "recovery_task_id": task.id if task else None, "recovery_status": task.status if task else None,
    }


def task_json(db: Session, t: RecoveryTask) -> dict:
    f = db.get(Feedback, t.feedback_id)
    v = db.get(Visit, f.visit_id) if f else None
    c = db.get(Customer, v.customer_id) if v else None
    b = db.get(Branch, v.branch_id) if v else None
    barber = db.get(Barber, v.barber_id) if v else None
    return {
        "id": t.id, "feedback_id": t.feedback_id, "visit_id": v.id if v else None,
        "customer_name": c.name if c else "Unknown", "branch_name": b.name if b else "Unknown",
        "barber_name": barber.name if barber else "Unknown", "rating": f.rating if f else None,
        "comment": f.comment if f else "", "status": t.status, "resolution_note": t.resolution_note,
        "created_at": t.created_at.isoformat(),
    }


def seed(db: Session, reset: bool = False):
    if reset:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    if db.query(Branch).count():
        return

    branches = [
        Branch(name="The Gentlemen's Club — Koregaon Park", location="Pune"),
        Branch(name="The Gentlemen's Club — Viman Nagar", location="Pune"),
        Branch(name="The Gentlemen's Club — Baner", location="Pune"),
    ]
    db.add_all(branches)
    db.flush()

    barbers = [
        Barber(branch_id=branches[0].id, name="Aarav Patil"),
        Barber(branch_id=branches[0].id, name="Rohan Jadhav"),
        Barber(branch_id=branches[1].id, name="Kabir Shah"),
        Barber(branch_id=branches[1].id, name="Dev Kulkarni"),
        Barber(branch_id=branches[2].id, name="Ishaan More"),
    ]
    customers = [
        Customer(name="Aditya Shah", phone="***-***-0142", messaging_consent=True),
        Customer(name="Neel Joshi", phone="***-***-0287", messaging_consent=True),
        Customer(name="Samir Desai", phone="***-***-0391", messaging_consent=True),
        Customer(name="Riya Demo", phone="***-***-0408", messaging_consent=True),
        Customer(name="Vikram Rao", phone="***-***-0523", messaging_consent=False),
        Customer(name="Kunal Mehta", phone="***-***-0664", messaging_consent=True),
    ]
    db.add_all(barbers + customers)
    db.flush()

    now = datetime.utcnow()
    samples = [
        (0, 0, 0, "Haircut + beard", 500, 1, 4, "Great experience. Asked for the same fade next time."),
        (1, 0, 1, "Haircut", 300, 3, 2, "The sides were uneven and I felt rushed."),
        (2, 1, 2, "Haircut", 350, 5, 5, "Very happy with the cut."),
        (3, 1, 3, "Haircut + wash", 450, 7, 3, "Waiting time was longer than expected."),
        (4, 2, 4, "Haircut", 300, 9, None, ""),
        (5, 0, 0, "Haircut", 300, 12, 1, "The shape was not what I requested."),
        (0, 1, 3, "Haircut", 300, 15, None, ""),
    ]
    for ci, bi, barber_index, service, amount, days, rating, comment in samples:
        v = Visit(
            customer_id=customers[ci].id, branch_id=branches[bi].id, barber_id=barbers[barber_index].id,
            service_name=service, amount=amount, completed_at=now - timedelta(days=days),
            feedback_requested=True,
        )
        db.add(v)
        db.flush()
        db.add(MessageLog(
            visit_id=v.id,
            status="mock_sent" if customers[ci].messaging_consent else "skipped_no_consent",
            message=message_for(customers[ci].name),
        ))
        if rating is not None:
            f = Feedback(
                visit_id=v.id, rating=rating, comment=comment,
                created_at=v.completed_at + timedelta(minutes=10),
            )
            db.add(f)
            db.flush()
            if rating <= 2:
                db.add(RecoveryTask(feedback_id=f.id, status="in_progress" if rating == 2 else "open"))
    db.commit()


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "SalonPulse API", "messaging": "mock_only"}


@app.get("/api/branches")
def get_branches(db: Session = Depends(get_db)):
    return [{"id": b.id, "name": b.name, "location": b.location}
            for b in db.query(Branch).order_by(Branch.name).all()]


@app.get("/api/barbers")
def get_barbers(branch_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Barber)
    if branch_id:
        q = q.filter_by(branch_id=branch_id)
    return [{"id": x.id, "name": x.name, "branch_id": x.branch_id}
            for x in q.order_by(Barber.name).all()]


@app.get("/api/customers")
def get_customers(db: Session = Depends(get_db)):
    out = []
    for c in db.query(Customer).order_by(Customer.name).all():
        count = db.query(Visit).filter_by(customer_id=c.id).count()
        last = db.query(Visit).filter_by(customer_id=c.id).order_by(Visit.completed_at.desc()).first()
        out.append({
            "id": c.id, "name": c.name, "phone": c.phone, "messaging_consent": c.messaging_consent,
            "visit_count": count, "last_visit": last.completed_at.isoformat() if last else None,
        })
    return out


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    visits = db.query(Visit).count()
    revenue = db.query(func.coalesce(func.sum(Visit.amount), 0)).scalar() or 0
    feedbacks = db.query(Feedback).all()
    low = sum(1 for f in feedbacks if f.rating <= 2)
    tasks = db.query(RecoveryTask).filter(RecoveryTask.status != "resolved").count()
    avg = sum(f.rating for f in feedbacks) / len(feedbacks) if feedbacks else None
    unique = db.query(Visit.customer_id).distinct().count()
    repeats = db.query(Visit.customer_id).group_by(Visit.customer_id).having(func.count(Visit.id) > 1).count()
    return {
        "total_visits": visits, "revenue": round(float(revenue), 2), "feedback_count": len(feedbacks),
        "low_feedback_count": low, "open_recovery_tasks": tasks,
        "average_rating": round(avg, 1) if avg else None,
        "feedback_response_rate": round(len(feedbacks) / visits * 100, 1) if visits else 0,
        "repeat_customer_rate": round(repeats / unique * 100, 1) if unique else 0,
        "branches": db.query(Branch).count(), "barbers": db.query(Barber).count(),
    }


@app.get("/api/visits")
def get_visits(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    return [visit_json(db, v)
            for v in db.query(Visit).order_by(Visit.completed_at.desc()).limit(limit).all()]


@app.post("/api/visits", status_code=201)
def create_visit(payload: VisitCreate, db: Session = Depends(get_db)):
    customer = db.get(Customer, payload.customer_id)
    branch = db.get(Branch, payload.branch_id)
    barber = db.get(Barber, payload.barber_id)
    if not customer or not branch or not barber:
        raise HTTPException(404, "Customer, branch, or barber not found")
    if barber.branch_id != branch.id:
        raise HTTPException(400, "Barber does not belong to the selected branch")
    if payload.messaging_consent:
        customer.messaging_consent = True
    v = Visit(
        customer_id=customer.id, branch_id=branch.id, barber_id=barber.id,
        service_name=payload.service_name, amount=payload.amount,
        feedback_requested=payload.messaging_consent,
    )
    db.add(v)
    db.flush()
    if payload.messaging_consent:
        db.add(MessageLog(visit_id=v.id, status="mock_queued", message=message_for(customer.name)))
    db.commit()
    db.refresh(v)
    return {
        "visit": visit_json(db, v),
        "message_status": "mock_queued" if payload.messaging_consent else "not_requested",
        "notice": "Demo only: no real WhatsApp message was sent.",
    }


@app.get("/api/feedback")
def get_feedback(db: Session = Depends(get_db)):
    return [feedback_json(db, f)
            for f in db.query(Feedback).order_by(Feedback.created_at.desc()).all()]


@app.post("/api/feedback", status_code=201)
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    v = db.get(Visit, payload.visit_id)
    if not v:
        raise HTTPException(404, "Visit not found")
    if db.query(Feedback).filter_by(visit_id=v.id).first():
        raise HTTPException(409, "Feedback already exists for this visit")
    f = Feedback(visit_id=v.id, rating=payload.rating, comment=payload.comment.strip())
    db.add(f)
    db.flush()
    if payload.rating <= 2:
        db.add(RecoveryTask(feedback_id=f.id, status="open"))
    db.commit()
    db.refresh(f)
    return {"feedback": feedback_json(db, f), "recovery_created": payload.rating <= 2}


@app.get("/api/recovery-tasks")
def get_tasks(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(RecoveryTask)
    if status:
        if status not in {"open", "in_progress", "resolved"}:
            raise HTTPException(400, "Invalid status")
        q = q.filter_by(status=status)
    return [task_json(db, t) for t in q.order_by(RecoveryTask.created_at.desc()).all()]


@app.patch("/api/recovery-tasks/{task_id}")
def update_task(task_id: int, payload: RecoveryUpdate, db: Session = Depends(get_db)):
    t = db.get(RecoveryTask, task_id)
    if not t:
        raise HTTPException(404, "Recovery task not found")
    t.status = payload.status
    t.resolution_note = payload.resolution_note.strip()
    db.commit()
    db.refresh(t)
    return task_json(db, t)


@app.get("/api/insights")
def get_insights(db: Session = Depends(get_db)):
    branch_rows = []
    for b in db.query(Branch).all():
        visits = db.query(Visit).filter_by(branch_id=b.id).all()
        feedbacks = db.query(Feedback).join(Visit, Visit.id == Feedback.visit_id).filter(Visit.branch_id == b.id).all()
        branch_rows.append({
            "branch_id": b.id, "branch_name": b.name, "visits": len(visits),
            "revenue": round(sum(v.amount for v in visits), 2), "feedback_count": len(feedbacks),
            "average_rating": round(sum(f.rating for f in feedbacks) / len(feedbacks), 1) if feedbacks else None,
            "low_rating_count": sum(1 for f in feedbacks if f.rating <= 2),
        })
    barber_rows = []
    for barber in db.query(Barber).all():
        visits = db.query(Visit).filter_by(barber_id=barber.id).all()
        feedbacks = db.query(Feedback).join(Visit, Visit.id == Feedback.visit_id).filter(Visit.barber_id == barber.id).all()
        branch = db.get(Branch, barber.branch_id)
        barber_rows.append({
            "barber_id": barber.id, "barber_name": barber.name,
            "branch_name": branch.name if branch else "", "visits": len(visits),
            "revenue": round(sum(v.amount for v in visits), 2), "feedback_count": len(feedbacks),
            "average_rating": round(sum(f.rating for f in feedbacks) / len(feedbacks), 1) if feedbacks else None,
        })
    return {"branches": branch_rows, "barbers": barber_rows}


@app.get("/api/messages")
def get_messages(db: Session = Depends(get_db)):
    out = []
    for m in db.query(MessageLog).order_by(MessageLog.created_at.desc()).all():
        v = db.get(Visit, m.visit_id)
        c = db.get(Customer, v.customer_id) if v else None
        out.append({
            "id": m.id, "visit_id": m.visit_id, "customer_name": c.name if c else "Unknown",
            "status": m.status, "message": m.message, "created_at": m.created_at.isoformat(),
            "channel": "whatsapp_mock",
        })
    return out


@app.post("/api/demo/reset")
def reset_demo():
    with SessionLocal() as db:
        seed(db, reset=True)
    return {"status": "ok", "message": "Demo data reset"}
