from __future__ import annotations

from datetime import datetime, timedelta
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# Vercel may package the FastAPI module at a different depth than the repo.
# Search the common repo/runtime locations instead of assuming frontend is a parent of ROOT.
APP_FILE = Path(__file__).resolve()
ROOT = APP_FILE.parents[1]
_FRONTEND_CANDIDATES = (
    ROOT.parent / "frontend",          # repository layout: backend/app/main.py
    Path.cwd() / "frontend",           # Vercel project-root layout
    APP_FILE.parent.parent / "frontend",  # flattened function bundle layout
)
FRONTEND = next(
    (candidate for candidate in _FRONTEND_CANDIDATES if (candidate / "index.html").is_file()),
    _FRONTEND_CANDIDATES[0],
)
DB = ROOT / "salonpulse.db"

def resolve_database_url() -> str:
    """Use Supabase/PostgreSQL when DATABASE_URL is configured; SQLite only for local dev."""
    configured = os.getenv("DATABASE_URL")
    if configured:
        if configured.startswith("postgres://"):
            configured = configured.replace("postgres://", "postgresql+psycopg://", 1)
        elif configured.startswith("postgresql://"):
            configured = configured.replace("postgresql://", "postgresql+psycopg://", 1)
        if configured.startswith("postgresql+psycopg://") and "sslmode=" not in configured:
            configured += ("&" if "?" in configured else "?") + "sslmode=require"
        return configured
    if os.getenv("VERCEL") == "1":
        raise RuntimeError(
            "DATABASE_URL is required on Vercel. Set it to the Supabase PostgreSQL connection string."
        )
    return f"sqlite:///{DB}"


DATABASE_URL = resolve_database_url()
engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    # Avoid prepared-statement reuse when the Supabase transaction pooler is used.
    engine_options["connect_args"] = {"prepare_threshold": None}
engine = create_engine(DATABASE_URL, **engine_options)
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
    location: Mapped[str] = mapped_column(String(160), default="")
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


class VisitService(Base):
    __tablename__ = "visit_services"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id", ondelete="CASCADE"))
    service_name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)
    line_total: Mapped[float] = mapped_column(Float)


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


class VisitServiceInput(BaseModel):
    service_name: str = Field(min_length=2, max_length=120)
    quantity: int = Field(ge=1, le=50)
    unit_price: float = Field(ge=0, le=100000)


class VisitCreate(BaseModel):
    customer_id: Optional[int] = None
    customer_name: Optional[str] = Field(default=None, max_length=120)
    customer_phone: Optional[str] = Field(default=None, max_length=40)
    customer_location: Optional[str] = Field(default="", max_length=160)
    branch_id: int
    barber_id: int
    services: list[VisitServiceInput] = Field(default_factory=list, max_length=10)
    # Legacy single-service fields remain accepted for older API clients.
    service_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    amount: Optional[float] = Field(default=None, ge=0, le=100000)
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

SERVICE_CATALOG = [
    {"name": "Haircut", "default_price": 300},
    {"name": "Beard Trim", "default_price": 150},
    {"name": "Haircut + Beard", "default_price": 450},
    {"name": "Hair Wash", "default_price": 100},
    {"name": "Hair Color", "default_price": 700},
]


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\\D", "", value or "")
    # Treat Indian 10-digit numbers and +91-prefixed numbers as the same phone.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def customer_json(db: Session, customer: Customer) -> dict:
    visits = db.query(Visit).filter_by(customer_id=customer.id)
    last = visits.order_by(Visit.completed_at.desc()).first()
    return {
        "id": customer.id, "name": customer.name, "phone": customer.phone,
        "location": customer.location or "", "messaging_consent": customer.messaging_consent,
        "visit_count": visits.count(), "last_visit": last.completed_at.isoformat() if last else None,
    }


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
    lines = db.query(VisitService).filter_by(visit_id=v.id).order_by(VisitService.id).all()
    service_items = [
        {"service_name": x.service_name, "quantity": x.quantity,
         "unit_price": x.unit_price, "line_total": x.line_total}
        for x in lines
    ]
    return {
        "id": v.id, "customer_id": v.customer_id, "customer_name": c.name if c else "Unknown",
        "customer_phone": c.phone if c else "", "customer_location": c.location if c else "",
        "branch_id": v.branch_id, "branch_name": b.name if b else "Unknown",
        "barber_id": v.barber_id, "barber_name": barber.name if barber else "Unknown",
        "service_name": v.service_name, "service_items": service_items, "amount": v.amount,
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
        # Delete demo rows in FK-safe order. Never drop/recreate production tables,
        # which would discard database grants and Row Level Security settings.
        for model in (MessageLog, RecoveryTask, Feedback, VisitService, Visit, Customer, Barber, Branch):
            db.query(model).delete(synchronize_session=False)
        db.commit()
    if db.query(Branch).count():
        return

    branches = [
        Branch(name="The Gentlemen's Club — Koregaon Park", location="Pune"),
        Branch(name="The Gentlemen's Club — Viman Nagar", location="Pune"),
        Branch(name="The Gentlemen's Club — Baner", location="Pune"),
        Branch(name="The Gentlemen's Club — Kalyani Nagar", location="Pune"),
    ]
    db.add_all(branches)
    db.flush()

    barbers = [
        Barber(branch_id=branches[0].id, name="Aarav Patil"),
        Barber(branch_id=branches[0].id, name="Rohan Jadhav"),
        Barber(branch_id=branches[1].id, name="Kabir Shah"),
        Barber(branch_id=branches[1].id, name="Dev Kulkarni"),
        Barber(branch_id=branches[2].id, name="Ishaan More"),
        Barber(branch_id=branches[3].id, name="Arjun Deshmukh"),
    ]
    customers = [
        # Seed customers are fictional; keep phone fields empty instead of using fake,
        # potentially callable numbers. Real customer details are entered in the form.
        Customer(name="Aditya Shah", phone="", location="Viman Nagar", messaging_consent=True),
        Customer(name="Neel Joshi", phone="", location="Kalyani Nagar", messaging_consent=True),
        Customer(name="Samir Desai", phone="", location="Koregaon Park", messaging_consent=True),
        Customer(name="Riya Demo", phone="", location="Kharadi", messaging_consent=True),
        Customer(name="Vikram Rao", phone="", location="Wagholi", messaging_consent=False),
        Customer(name="Kunal Mehta", phone="", location="Baner", messaging_consent=True),
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
        db.add(VisitService(
            visit_id=v.id, service_name=service, quantity=1,
            unit_price=float(amount), line_total=float(amount),
        ))
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


@app.get("/api/service-catalog")
def get_service_catalog():
    return SERVICE_CATALOG


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


@app.get("/api/customers/search")
def search_customers(q: str = Query(min_length=1, max_length=120), db: Session = Depends(get_db)):
    term = q.strip()
    digits = normalize_phone(term)
    customers = db.query(Customer).order_by(Customer.name).all()
    matches = []
    for c in customers:
        name_match = term.casefold() in c.name.casefold()
        phone_digits = normalize_phone(c.phone)
        phone_match = bool(digits) and (
            phone_digits == digits or (len(digits) >= 3 and digits in phone_digits)
        )
        if name_match or phone_match:
            matches.append(c)
    if digits:
        matches.sort(key=lambda c: normalize_phone(c.phone) != digits)
    return [customer_json(db, c) for c in matches[:10]]


@app.get("/api/customers")
def get_customers(db: Session = Depends(get_db)):
    return [customer_json(db, c) for c in db.query(Customer).order_by(Customer.name).all()]


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
    branch = db.get(Branch, payload.branch_id)
    barber = db.get(Barber, payload.barber_id)
    if not branch or not barber:
        raise HTTPException(404, "Branch or barber not found")
    if barber.branch_id != branch.id:
        raise HTTPException(400, "Barber does not belong to the selected branch")

    if payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(404, "Customer not found. Search again and select a customer.")
    else:
        customer_name = (payload.customer_name or "").strip()
        customer_phone = (payload.customer_phone or "").strip()
        customer_location = (payload.customer_location or "").strip()
        normalized_phone = normalize_phone(customer_phone)
        if len(normalized_phone) < 7 or len(normalized_phone) > 15:
            raise HTTPException(400, "Enter a valid customer phone number (7–15 digits).")
        if not customer_name:
            raise HTTPException(400, "Customer name is required for a new customer.")
        for existing in db.query(Customer).all():
            if normalized_phone and normalize_phone(existing.phone) == normalized_phone:
                raise HTTPException(
                    409,
                    f"This phone number already belongs to {existing.name}. Search for the returning customer and confirm the match."
                )
        customer = Customer(name=customer_name, phone=customer_phone, location=customer_location)
        db.add(customer)
        db.flush()

    service_inputs = payload.services
    if not service_inputs:
        # Backward compatibility for older clients that submit a single service/amount.
        if not payload.service_name or payload.amount is None:
            raise HTTPException(400, "Add at least one service.")
        service_inputs = [VisitServiceInput(
            service_name=payload.service_name, quantity=1, unit_price=payload.amount
        )]
    total_amount = round(sum(item.quantity * item.unit_price for item in service_inputs), 2)
    service_summary = " + ".join(
        f"{item.service_name} ×{item.quantity}" if item.quantity > 1 else item.service_name
        for item in service_inputs
    )
    if payload.messaging_consent:
        customer.messaging_consent = True

    v = Visit(
        customer_id=customer.id, branch_id=branch.id, barber_id=barber.id,
        service_name=service_summary, amount=total_amount,
        feedback_requested=payload.messaging_consent,
    )
    db.add(v)
    db.flush()
    for item in service_inputs:
        line_total = round(item.quantity * item.unit_price, 2)
        db.add(VisitService(
            visit_id=v.id, service_name=item.service_name, quantity=item.quantity,
            unit_price=item.unit_price, line_total=line_total,
        ))
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
