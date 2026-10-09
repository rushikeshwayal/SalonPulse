from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, and_, case, create_engine, func, or_
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


class StaffUser(Base):
    __tablename__ = "staff_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    barber_id: Mapped[Optional[int]] = mapped_column(ForeignKey("barbers.id"), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40), default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    messaging_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_users.id"), nullable=True)


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
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_users.id"), nullable=True)


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


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    actor_username: Mapped[str] = mapped_column(String(80))
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int] = mapped_column(Integer)
    before_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    change_note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomerRating(Base):
    __tablename__ = "customer_ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id", ondelete="CASCADE"), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    barber_user_id: Mapped[int] = mapped_column(ForeignKey("staff_users.id"))
    rating: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    # Browser sends an ISO 8601 timestamp with its offset; store in UTC.
    completed_at: Optional[datetime] = None
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


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class VisitUpdate(BaseModel):
    branch_id: Optional[int] = None
    barber_id: Optional[int] = None
    customer_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    services: Optional[list[VisitServiceInput]] = Field(default=None, max_length=10)
    messaging_consent: Optional[bool] = None
    change_note: str = Field(default="", max_length=500)


class CustomerRatingCreate(BaseModel):
    visit_id: int
    rating: int = Field(ge=1, le=5)
    note: str = Field(default="", max_length=1000)


app = FastAPI(
    title="SalonPulse API",
    version="0.1.0",
    description="Salon feedback and service recovery demo. Messaging is mock-only.",
)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

AUTH_SECRET = os.getenv("APP_AUTH_SECRET")
if os.getenv("VERCEL") == "1" and not AUTH_SECRET:
    raise RuntimeError("APP_AUTH_SECRET must be configured for production authentication.")
AUTH_SECRET = AUTH_SECRET or "local-development-only-not-for-production"
TOKEN_TTL_SECONDS = 8 * 60 * 60
PBKDF2_ITERATIONS = 420_000


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(18)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${b64url(salt)}${b64url(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = b64url_decode(salt_text)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(b64url(candidate), expected)
    except (ValueError, TypeError):
        return False


def user_public(user: StaffUser) -> dict:
    barber = None
    if user.barber_id:
        with SessionLocal() as db:
            barber = db.get(Barber, user.barber_id)
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "display_name": user.display_name, "role": user.role, "barber_id": user.barber_id,
        "branch_id": barber.branch_id if barber else None,
        "is_active": user.is_active, "must_change_password": user.must_change_password,
    }


def create_access_token(user: StaffUser) -> str:
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64url(json.dumps({
        "sub": str(user.id), "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "iat": int(time.time()), "nonce": secrets.token_urlsafe(8),
    }, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode()
    signature = hmac.new(AUTH_SECRET.encode(), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{b64url(signature)}"


def verify_access_token(token: str) -> Optional[dict]:
    try:
        header_text, payload_text, signature_text = token.split(".")
        header = json.loads(b64url_decode(header_text))
        if header.get("alg") != "HS256":
            return None
        message = f"{header_text}.{payload_text}".encode()
        expected = b64url(hmac.new(AUTH_SECRET.encode(), message, hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature_text):
            return None
        payload = json.loads(b64url_decode(payload_text))
        if int(payload.get("exp", 0)) <= int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def actor_view(user: StaffUser) -> dict:
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "display_name": user.display_name, "role": user.role,
        "barber_id": user.barber_id, "must_change_password": user.must_change_password,
    }


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if (
        path == "/" or path == "/api/health" or path == "/api/auth/login"
        or path.startswith("/static/") or request.method == "OPTIONS"
    ):
        return await call_next(request)
    if not path.startswith("/api/") and path not in {"/docs", "/redoc", "/openapi.json"}:
        return await call_next(request)
    auth_header = request.headers.get("authorization", "")
    token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
    claims = verify_access_token(token) if token else None
    if not claims:
        return JSONResponse(status_code=401, content={"detail": "Please sign in to continue."},
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = int(claims.get("sub", "0"))
    except (ValueError, TypeError):
        user_id = 0
    with SessionLocal() as db:
        user = db.get(StaffUser, user_id)
        if not user or not user.is_active:
            return JSONResponse(status_code=401, content={"detail": "This account is not active."})
        if user.must_change_password and path not in {"/api/auth/me", "/api/auth/change-password"}:
            return JSONResponse(status_code=403, content={"detail": "PASSWORD_CHANGE_REQUIRED: Update your temporary password first."})
        request.state.user = actor_view(user)
    return await call_next(request)


def get_current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


def require_owner(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner access required.")
    return user


def add_audit(db: Session, actor: dict, action: str, entity_type: str, entity_id: int,
              before_data: Optional[dict], after_data: Optional[dict], change_note: str = "") -> None:
    db.add(AuditLog(
        actor_user_id=actor["id"], actor_username=actor["username"], actor_role=actor["role"],
        action=action, entity_type=entity_type, entity_id=entity_id,
        before_data=before_data, after_data=after_data, change_note=change_note,
    ))

SERVICE_CATALOG = [
    {"name": "Haircut", "default_price": 300},
    {"name": "Beard Trim", "default_price": 150},
    {"name": "Haircut + Beard", "default_price": 450},
    {"name": "Hair Wash", "default_price": 100},
    {"name": "Hair Color", "default_price": 700},
]


def normalize_phone(value: str | None) -> str:
    digits = re.sub("[^0-9]", "", value or "")
    # Treat Indian 10-digit numbers and +91-prefixed numbers as the same phone.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def utc_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def customer_json(db: Session, customer: Customer) -> dict:
    visits = db.query(Visit).filter_by(customer_id=customer.id)
    last = visits.order_by(Visit.completed_at.desc()).first()
    return {
        "id": customer.id, "name": customer.name, "phone": customer.phone,
        "location": customer.location or "", "messaging_consent": customer.messaging_consent,
        "visit_count": visits.count(), "last_visit": (last.completed_at.isoformat() + "Z") if last and last.completed_at.tzinfo is None else (last.completed_at.isoformat() if last else None),
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
        "completed_at": (v.completed_at.isoformat() + "Z") if v.completed_at.tzinfo is None else v.completed_at.isoformat(), "feedback_requested": v.feedback_requested,
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


def seed_demo_users(db: Session) -> None:
    seeds = [
        ("owner", "owner@salonpulse.demo", "SalonPulse Owner", "owner", None,
         "pbkdf2_sha256$420000$rgc7iELvo2Hh0ct31Qr9cfG7$YoHf6h5XjLIguUMwtydvEbRQtcgRqt3HvXebYcKl2RE"),
        ("aarav", "aarav.patil@salonpulse.demo", "Aarav Patil", "barber", 1,
         "pbkdf2_sha256$420000$w7zWB5HuL6yCKqWbXu2yRgz8$-8vxoyUebQVitxwpzC8TQRqQ4OC3Wb_6-mXy8bTOo_o"),
        ("rohan", "rohan.jadhav@salonpulse.demo", "Rohan Jadhav", "barber", 2,
         "pbkdf2_sha256$420000$NKRdXyBel7zv7Ww_58_TS3Vx$n5mizeA-wYAOYGDVaHGZMrMH1XHm-OEwFWJtKXCatrU"),
        ("kabir", "kabir.shah@salonpulse.demo", "Kabir Shah", "barber", 3,
         "pbkdf2_sha256$420000$jbYrAb3Nwep9jJIqcFUFLiVV$7VO-yklqk_Dmlvao57KGYydVGCQZAc4frUer9R7bivM"),
        ("dev", "dev.kulkarni@salonpulse.demo", "Dev Kulkarni", "barber", 4,
         "pbkdf2_sha256$420000$rJ6-JDSluWWFx4EHUkK9tc8I$jNZecAvQETD_63p-yr3AfBCme1Yy_-K4eMOa_R_7aYo"),
        ("ishaan", "ishaan.more@salonpulse.demo", "Ishaan More", "barber", 5,
         "pbkdf2_sha256$420000$gCGjppxtE6oTzRJJiYnBRVmd$Pfkor6KFoFIcoWmrwFk6bNj8-HvglCQ4rIoNh4rvFNw"),
        ("arjun", "arjun.deshmukh@salonpulse.demo", "Arjun Deshmukh", "barber", 6,
         "pbkdf2_sha256$420000$VhPB6_LQmQFGtrNh9RSq7qsN$76dVSlme0o1BDB-K-N5QmiUzOdxhtqoTbhay6aCK4dc"),
    ]
    for username, email, display_name, role, barber_id, password_hash_value in seeds:
        exists = db.query(StaffUser.id).filter(
            or_(StaffUser.username == username, StaffUser.email == email)
        ).first()
        if not exists:
            db.add(StaffUser(
                username=username, email=email, display_name=display_name, role=role,
                barber_id=barber_id, password_hash=password_hash_value,
                is_active=True, must_change_password=True,
            ))
    db.commit()


def seed(db: Session, reset: bool = False):
    if reset:
        # Delete demo rows in FK-safe order. Never drop/recreate production tables,
        # which would discard database grants and Row Level Security settings.
        for model in (MessageLog, RecoveryTask, Feedback, VisitService, Visit, Customer, Barber, Branch):
            db.query(model).delete(synchronize_session=False)
        db.commit()
    if db.query(Branch).count():
        seed_demo_users(db)
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
    seed_demo_users(db)


@app.on_event("startup")
def startup():
    # Local SQLite is self-contained, so create/seed its demo schema on startup.
    # Production Postgres is managed by checked-in Supabase migrations; avoid schema
    # introspection and demo-seed queries on every serverless cold start.
    if DATABASE_URL.startswith("sqlite:"):
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed(db)


@app.post("/api/auth/login")
def auth_login(payload: LoginRequest, db: Session = Depends(get_db)):
    identifier = payload.identifier.strip().casefold()
    user = db.query(StaffUser).filter(
        or_(func.lower(StaffUser.username) == identifier, func.lower(StaffUser.email) == identifier)
    ).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username/email or password.")
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": actor_view(user),
        "expires_in": TOKEN_TTL_SECONDS,
    }


@app.get("/api/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    return user


@app.post("/api/auth/change-password")
def auth_change_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    record = db.get(StaffUser, user["id"])
    if not record or not verify_password(payload.current_password, record.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="Choose a different new password.")
    before = {"must_change_password": record.must_change_password}
    record.password_hash = hash_password(payload.new_password)
    record.must_change_password = False
    record.updated_at = datetime.utcnow()
    add_audit(db, user, "credential.change", "staff_user", record.id, before,
              {"must_change_password": False}, "Password changed by account holder")
    db.commit()
    return {"status": "ok", "user": {**user, "must_change_password": False}}


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
    # Reuse the batched customer/visit summary query; no per-result database queries.
    customers = get_customers(db)
    matches = []
    for customer in customers:
        name_match = term.casefold() in customer["name"].casefold()
        phone_digits = normalize_phone(customer["phone"])
        phone_match = bool(digits) and (
            phone_digits == digits or (len(digits) >= 3 and digits in phone_digits)
        )
        if name_match or phone_match:
            matches.append(customer)
    if digits:
        matches.sort(key=lambda customer: normalize_phone(customer["phone"]) != digits)
    return matches[:10]


@app.get("/api/customers")
def get_customers(db: Session = Depends(get_db)):
    # Fetch visit counts and most recent visit once instead of two queries per customer.
    stats = db.query(
        Visit.customer_id,
        func.count(Visit.id).label("visit_count"),
        func.max(Visit.completed_at).label("last_visit"),
    ).group_by(Visit.customer_id).all()
    by_customer = {row.customer_id: row for row in stats}
    customers = db.query(Customer).order_by(Customer.name).all()
    result = []
    for customer in customers:
        row = by_customer.get(customer.id)
        result.append({
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "location": customer.location or "",
            "messaging_consent": customer.messaging_consent,
            "visit_count": int(row.visit_count) if row else 0,
            "last_visit": utc_iso(row.last_visit) if row else None,
        })
    return result

@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    visit_row = db.query(
        func.count(Visit.id),
        func.coalesce(func.sum(Visit.amount), 0),
    ).one()
    feedback_row = db.query(
        func.count(Feedback.id),
        func.avg(Feedback.rating),
        func.coalesce(func.sum(case((Feedback.rating <= 2, 1), else_=0)), 0),
    ).one()
    open_tasks = db.query(func.count(RecoveryTask.id)).filter(
        RecoveryTask.status != "resolved"
    ).scalar() or 0
    unique = db.query(func.count(func.distinct(Visit.customer_id))).scalar() or 0
    repeat_rows = db.query(Visit.customer_id).group_by(Visit.customer_id).having(
        func.count(Visit.id) > 1
    ).subquery()
    repeats = db.query(func.count()).select_from(repeat_rows).scalar() or 0
    visit_count, revenue = int(visit_row[0]), float(visit_row[1] or 0)
    feedback_count, average_rating, low_count = feedback_row
    return {
        "total_visits": visit_count,
        "revenue": round(revenue, 2),
        "feedback_count": int(feedback_count),
        "low_feedback_count": int(low_count),
        "open_recovery_tasks": int(open_tasks),
        "average_rating": round(float(average_rating), 1) if average_rating is not None else None,
        "feedback_response_rate": round(feedback_count / visit_count * 100, 1) if visit_count else 0,
        "repeat_customer_rate": round(repeats / unique * 100, 1) if unique else 0,
        "branches": db.query(func.count(Branch.id)).scalar() or 0,
        "barbers": db.query(func.count(Barber.id)).scalar() or 0,
    }

@app.get("/api/visits")
def get_visits(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    # Join related data in one query. Fetch all service lines in one additional query.
    rows = db.query(Visit, Customer, Branch, Barber, Feedback).join(
        Customer, Customer.id == Visit.customer_id
    ).join(
        Branch, Branch.id == Visit.branch_id
    ).join(
        Barber, Barber.id == Visit.barber_id
    ).outerjoin(
        Feedback, Feedback.visit_id == Visit.id
    ).order_by(Visit.completed_at.desc()).limit(limit).all()
    visit_ids = [row[0].id for row in rows]
    service_map = {}
    if visit_ids:
        service_rows = db.query(VisitService).filter(
            VisitService.visit_id.in_(visit_ids)
        ).order_by(VisitService.id).all()
        for service in service_rows:
            service_map.setdefault(service.visit_id, []).append({
                "service_name": service.service_name,
                "quantity": service.quantity,
                "unit_price": service.unit_price,
                "line_total": service.line_total,
            })
    return [{
        "id": visit.id,
        "customer_id": customer.id,
        "customer_name": customer.name,
        "customer_phone": customer.phone,
        "customer_location": customer.location or "",
        "branch_id": branch.id,
        "branch_name": branch.name,
        "barber_id": barber.id,
        "barber_name": barber.name,
        "service_name": visit.service_name,
        "service_items": service_map.get(visit.id, []),
        "amount": visit.amount,
        "completed_at": utc_iso(visit.completed_at),
        "feedback_requested": visit.feedback_requested,
        "feedback_received": feedback is not None,
        "rating": feedback.rating if feedback else None,
    } for visit, customer, branch, barber, feedback in rows]

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

    # Interpret a missing timestamp as now; normalize supplied local-offset
    # timestamps to naive UTC for PostgreSQL's timestamp-without-time-zone column.
    visited_at = payload.completed_at or datetime.now(timezone.utc)
    if visited_at.tzinfo is None:
        visited_at = visited_at.replace(tzinfo=timezone.utc)
    visited_at = visited_at.astimezone(timezone.utc).replace(tzinfo=None)

    v = Visit(
        customer_id=customer.id, branch_id=branch.id, barber_id=barber.id,
        service_name=service_summary, amount=total_amount, completed_at=visited_at,
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
def get_feedback(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.query(Feedback, Visit, Customer, Branch, Barber, RecoveryTask).join(
        Visit, Visit.id == Feedback.visit_id
    ).join(
        Customer, Customer.id == Visit.customer_id
    ).join(
        Branch, Branch.id == Visit.branch_id
    ).join(
        Barber, Barber.id == Visit.barber_id
    ).outerjoin(
        RecoveryTask, RecoveryTask.feedback_id == Feedback.id
    ).order_by(Feedback.created_at.desc()).limit(limit).all()
    return [{
        "id": feedback.id,
        "visit_id": visit.id,
        "customer_name": customer.name,
        "branch_name": branch.name,
        "barber_name": barber.name,
        "rating": feedback.rating,
        "comment": feedback.comment,
        "created_at": utc_iso(feedback.created_at),
        "recovery_task_id": task.id if task else None,
        "recovery_status": task.status if task else None,
    } for feedback, visit, customer, branch, barber, task in rows]

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
def get_tasks(
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(RecoveryTask, Feedback, Visit, Customer, Branch, Barber).join(
        Feedback, Feedback.id == RecoveryTask.feedback_id
    ).join(
        Visit, Visit.id == Feedback.visit_id
    ).join(
        Customer, Customer.id == Visit.customer_id
    ).join(
        Branch, Branch.id == Visit.branch_id
    ).join(
        Barber, Barber.id == Visit.barber_id
    )
    if status:
        if status not in {"open", "in_progress", "resolved"}:
            raise HTTPException(400, "Invalid status")
        query = query.filter(RecoveryTask.status == status)
    rows = query.order_by(RecoveryTask.created_at.desc()).limit(limit).all()
    return [{
        "id": task.id,
        "feedback_id": feedback.id,
        "visit_id": visit.id,
        "customer_name": customer.name,
        "branch_name": branch.name,
        "barber_name": barber.name,
        "rating": feedback.rating,
        "comment": feedback.comment,
        "status": task.status,
        "resolution_note": task.resolution_note,
        "created_at": utc_iso(task.created_at),
    } for task, feedback, visit, customer, branch, barber in rows]

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
    # Aggregate in SQL; don't load every visit and feedback row per branch/barber.
    branch_rows = db.query(
        Branch.id.label("branch_id"),
        Branch.name.label("branch_name"),
        func.count(Visit.id).label("visits"),
        func.coalesce(func.sum(Visit.amount), 0).label("revenue"),
        func.count(Feedback.id).label("feedback_count"),
        func.avg(Feedback.rating).label("average_rating"),
        func.coalesce(func.sum(case((Feedback.rating <= 2, 1), else_=0)), 0).label("low_rating_count"),
    ).outerjoin(
        Visit, Visit.branch_id == Branch.id
    ).outerjoin(
        Feedback, Feedback.visit_id == Visit.id
    ).group_by(Branch.id, Branch.name).all()
    barber_rows = db.query(
        Barber.id.label("barber_id"),
        Barber.name.label("barber_name"),
        Branch.name.label("branch_name"),
        func.count(Visit.id).label("visits"),
        func.coalesce(func.sum(Visit.amount), 0).label("revenue"),
        func.count(Feedback.id).label("feedback_count"),
        func.avg(Feedback.rating).label("average_rating"),
    ).join(
        Branch, Branch.id == Barber.branch_id
    ).outerjoin(
        Visit, Visit.barber_id == Barber.id
    ).outerjoin(
        Feedback, Feedback.visit_id == Visit.id
    ).group_by(Barber.id, Barber.name, Branch.name).all()
    return {
        "branches": [{
            "branch_id": row.branch_id,
            "branch_name": row.branch_name,
            "visits": int(row.visits),
            "revenue": round(float(row.revenue or 0), 2),
            "feedback_count": int(row.feedback_count),
            "average_rating": round(float(row.average_rating), 1) if row.average_rating is not None else None,
            "low_rating_count": int(row.low_rating_count),
        } for row in branch_rows],
        "barbers": [{
            "barber_id": row.barber_id,
            "barber_name": row.barber_name,
            "branch_name": row.branch_name,
            "visits": int(row.visits),
            "revenue": round(float(row.revenue or 0), 2),
            "feedback_count": int(row.feedback_count),
            "average_rating": round(float(row.average_rating), 1) if row.average_rating is not None else None,
        } for row in barber_rows],
    }

@app.get("/api/messages")
def get_messages(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)):
    rows = db.query(MessageLog, Visit, Customer).join(
        Visit, Visit.id == MessageLog.visit_id
    ).join(
        Customer, Customer.id == Visit.customer_id
    ).order_by(MessageLog.created_at.desc()).limit(limit).all()
    return [{
        "id": message.id,
        "visit_id": visit.id,
        "customer_name": customer.name,
        "status": message.status,
        "message": message.message,
        "created_at": utc_iso(message.created_at),
        "channel": "whatsapp_mock",
    } for message, visit, customer in rows]

@app.post("/api/demo/reset")
def reset_demo():
    with SessionLocal() as db:
        seed(db, reset=True)
    return {"status": "ok", "message": "Demo data reset"}

@app.get("/api/bootstrap")
def bootstrap(db: Session = Depends(get_db)):
    """One round-trip for the first dashboard paint; subroutes still work independently."""
    return {
        "dashboard": dashboard(db),
        "branches": get_branches(db),
        "barbers": get_barbers(None, db),
        "customers": get_customers(db),
        "visits": get_visits(20, db),
        "feedback": get_feedback(20, db),
        "tasks": get_tasks(None, 20, db),
        "insights": get_insights(db),
        "messages": get_messages(10, db),
        "serviceCatalog": get_service_catalog(),
    }

