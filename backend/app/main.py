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
         "pbkdf2_sha256$420000$23iYiCHmItKShez99fmXmWPU$5OIytF91x0M09r_5_-HPzAaFUpr53TIDCoJZ4auk8W0"),
        ("aarav", "aarav.patil@salonpulse.demo", "Aarav Patil", "barber", 1,
         "pbkdf2_sha256$420000$Qaxp9eRhlRvi95K0pwEIOerl$6dtYYrJLsRMuyckc0QrZUw2uVbDNHXiYQgZIodmylDw"),
        ("rohan", "rohan.jadhav@salonpulse.demo", "Rohan Jadhav", "barber", 2,
         "pbkdf2_sha256$420000$4CGHxqs1t5TvPNezMXpOxWrV$otoUciAgH-RfsFidVrHA6yl4U7VwekLUxfAfTsYYSCU"),
        ("kabir", "kabir.shah@salonpulse.demo", "Kabir Shah", "barber", 3,
         "pbkdf2_sha256$420000$s-1scbpsXi1XGG97_YYf8iOw$TbVmDvb1Jv6ecXjqiauQHhP51w8axIB-JP9X7w2ToII"),
        ("dev", "dev.kulkarni@salonpulse.demo", "Dev Kulkarni", "barber", 4,
         "pbkdf2_sha256$420000$sU6ogeeSBNbNNuBcv1k4ncb7$SzGgO-3Iyq0BG_ao6Y8DZV5BUDOUyamWlWDjZlkoUbs"),
        ("ishaan", "ishaan.more@salonpulse.demo", "Ishaan More", "barber", 5,
         "pbkdf2_sha256$420000$CtK1t4WZEPW3-WIIudz8sZjZ$9qwhrAFtPRqzAzcgtSLLCnf2tjvtZJmfx0_3E3IiXNM"),
        ("arjun", "arjun.deshmukh@salonpulse.demo", "Arjun Deshmukh", "barber", 6,
         "pbkdf2_sha256$420000$M1u_l-lwKUC3Nnc5wn7o4G-s$ibaVw8SeZKJVk51D7h8vXmC33IfJTplRKTpLRK5Mx9c"),
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
        for model in (AuditLog, CustomerRating, MessageLog, RecoveryTask, Feedback, VisitService, Visit, Customer):
            db.query(model).delete(synchronize_session=False)
        db.commit()
    if db.query(Customer).count() and db.query(Visit).count():
        seed_demo_users(db)
        return

    branches = db.query(Branch).order_by(Branch.id).all()
    if not branches:
        branches = [
            Branch(name="The Gentlemen's Club — Koregaon Park", location="Pune"),
            Branch(name="The Gentlemen's Club — Viman Nagar", location="Pune"),
            Branch(name="The Gentlemen's Club — Baner", location="Pune"),
            Branch(name="The Gentlemen's Club — Kalyani Nagar", location="Pune"),
        ]
        db.add_all(branches)
        db.flush()

    barbers = db.query(Barber).order_by(Barber.id).all()
    if not barbers:
        barbers = [
            Barber(branch_id=branches[0].id, name="Aarav Patil"),
            Barber(branch_id=branches[0].id, name="Rohan Jadhav"),
            Barber(branch_id=branches[1].id, name="Kabir Shah"),
            Barber(branch_id=branches[1].id, name="Dev Kulkarni"),
            Barber(branch_id=branches[2].id, name="Ishaan More"),
            Barber(branch_id=branches[3].id, name="Arjun Deshmukh"),
        ]
        db.add_all(barbers)
        db.flush()
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


def branch_id_for_user(db: Session, user: dict) -> Optional[int]:
    if user["role"] == "owner":
        return None
    barber = db.get(Barber, user.get("barber_id"))
    return barber.branch_id if barber else None


def check_visit_access(visit: Visit, user: dict) -> None:
    if user["role"] == "barber" and visit.barber_id != user.get("barber_id"):
        raise HTTPException(status_code=403, detail="You can only access visits assigned to your barber account.")


def latest_customer_visit_id(db: Session, customer_id: int) -> Optional[int]:
    latest = db.query(Visit.id).filter(
        Visit.customer_id == customer_id
    ).order_by(Visit.completed_at.desc(), Visit.id.desc()).first()
    return latest[0] if latest else None


def check_latest_visit_editable(db: Session, visit: Visit) -> None:
    latest_id = latest_customer_visit_id(db, visit.customer_id)
    if latest_id != visit.id:
        raise HTTPException(
            status_code=409,
            detail="This is an older customer visit and is read-only. Only the customer's latest visit can be edited.",
        )


def visible_customers_query(db: Session, user: dict):
    query = db.query(Customer)
    if user["role"] == "barber":
        # A barber's customer directory is limited to people they personally served.
        visit_customer_ids = db.query(Visit.customer_id).filter(
            Visit.barber_id == user["barber_id"]
        ).distinct()
        query = query.filter(Customer.id.in_(visit_customer_ids))
    return query


def customer_rows(db: Session, user: dict) -> list[dict]:
    visits_query = db.query(
        Visit.customer_id, func.count(Visit.id).label("visit_count"),
        func.max(Visit.completed_at).label("last_visit"),
    )
    if user["role"] == "barber":
        visits_query = visits_query.filter(Visit.barber_id == user["barber_id"])
    stats = visits_query.group_by(Visit.customer_id).all()
    stats_map = {row.customer_id: row for row in stats}
    result = []
    for c in visible_customers_query(db, user).order_by(Customer.name).all():
        row = stats_map.get(c.id)
        result.append({
            "id": c.id, "name": c.name, "phone": c.phone, "location": c.location or "",
            "messaging_consent": c.messaging_consent,
            "visit_count": int(row.visit_count) if row else 0,
            "last_visit": utc_iso(row.last_visit) if row else None,
        })
    return result


def branch_rows(db: Session, user: dict) -> list[dict]:
    query = db.query(Branch)
    if user["role"] == "barber":
        query = query.filter(Branch.id == branch_id_for_user(db, user))
    return [{"id": b.id, "name": b.name, "location": b.location}
            for b in query.order_by(Branch.name).all()]


def barber_rows(db: Session, user: dict) -> list[dict]:
    query = db.query(Barber)
    if user["role"] == "barber":
        query = query.filter(Barber.id == user["barber_id"])
    return [{"id": b.id, "name": b.name, "branch_id": b.branch_id}
            for b in query.order_by(Barber.name).all()]


def visit_rows(db: Session, user: dict, limit: int = 20) -> list[dict]:
    query = db.query(Visit, Customer, Branch, Barber, Feedback, CustomerRating).join(
        Customer, Customer.id == Visit.customer_id
    ).join(Branch, Branch.id == Visit.branch_id).join(
        Barber, Barber.id == Visit.barber_id
    ).outerjoin(Feedback, Feedback.visit_id == Visit.id).outerjoin(
        CustomerRating, CustomerRating.visit_id == Visit.id
    )
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(Visit.completed_at.desc(), Visit.id.desc()).limit(limit).all()
    visit_ids = [v.id for v, *_ in rows]
    # Sequence numbers and edit eligibility are calculated across the full customer history,
    # not just the latest page of results or the currently signed-in barber's visible visits.
    history_rows = db.query(Visit.id, Visit.customer_id).order_by(
        Visit.completed_at.desc(), Visit.id.desc()
    ).all()
    customer_sequence: dict[int, dict[int, dict[str, int | bool]]] = {}
    per_customer: dict[int, list[int]] = {}
    for history_visit_id, customer_id in history_rows:
        per_customer.setdefault(customer_id, []).append(history_visit_id)
    for customer_id, ids in per_customer.items():
        total = len(ids)
        customer_sequence[customer_id] = {
            history_visit_id: {
                "visit_number": total - index,
                "visit_count": total,
                "is_latest_visit": index == 0,
            }
            for index, history_visit_id in enumerate(ids)
        }
    service_map: dict[int, list[dict]] = {}
    if visit_ids:
        for line in db.query(VisitService).filter(VisitService.visit_id.in_(visit_ids)).order_by(VisitService.id).all():
            service_map.setdefault(line.visit_id, []).append({
                "service_name": line.service_name, "quantity": line.quantity,
                "unit_price": line.unit_price, "line_total": line.line_total,
            })
    return [{
        "id": v.id, "customer_id": c.id, "customer_name": c.name,
        "customer_phone": c.phone, "customer_location": c.location or "",
        "branch_id": b.id, "branch_name": b.name, "barber_id": barber.id, "barber_name": barber.name,
        "service_name": v.service_name, "service_items": service_map.get(v.id, []),
        "amount": v.amount, "completed_at": utc_iso(v.completed_at),
        "feedback_requested": v.feedback_requested, "feedback_received": f is not None,
        "rating": f.rating if f else None, "feedback_comment": f.comment if f else None,
        "feedback_created_at": utc_iso(f.created_at) if f else None,
        "customer_rating": cr.rating if cr else None,
        "customer_rating_note": cr.note if cr else "",
        **customer_sequence.get(v.customer_id, {}).get(v.id, {
            "visit_number": 1, "visit_count": 1, "is_latest_visit": True,
        }),
        "can_edit": (
            customer_sequence.get(v.customer_id, {}).get(v.id, {}).get("is_latest_visit", False)
            and (user["role"] == "owner" or v.barber_id == user.get("barber_id"))
        ),
    } for v, c, b, barber, f, cr in rows]


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


def feedback_rows(db: Session, user: dict, limit: int = 20) -> list[dict]:
    query = db.query(Feedback, Visit, Customer, Branch, Barber, RecoveryTask).join(
        Visit, Visit.id == Feedback.visit_id
    ).join(Customer, Customer.id == Visit.customer_id).join(
        Branch, Branch.id == Visit.branch_id
    ).join(Barber, Barber.id == Visit.barber_id).outerjoin(
        RecoveryTask, RecoveryTask.feedback_id == Feedback.id
    )
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(Feedback.created_at.desc()).limit(limit).all()
    return [{
        "id": f.id, "visit_id": v.id, "customer_name": c.name, "branch_name": b.name,
        "barber_name": barber.name, "rating": f.rating, "comment": f.comment,
        "created_at": utc_iso(f.created_at), "recovery_task_id": t.id if t else None,
        "recovery_status": t.status if t else None,
    } for f, v, c, b, barber, t in rows]


def task_rows(db: Session, user: dict, limit: int = 20) -> list[dict]:
    query = db.query(RecoveryTask, Feedback, Visit, Customer, Branch, Barber).join(
        Feedback, Feedback.id == RecoveryTask.feedback_id
    ).join(Visit, Visit.id == Feedback.visit_id).join(
        Customer, Customer.id == Visit.customer_id
    ).join(Branch, Branch.id == Visit.branch_id).join(
        Barber, Barber.id == Visit.barber_id
    )
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(RecoveryTask.created_at.desc()).limit(limit).all()
    return [{
        "id": t.id, "feedback_id": f.id, "visit_id": v.id, "customer_name": c.name,
        "branch_name": b.name, "barber_name": barber.name, "rating": f.rating,
        "comment": f.comment, "status": t.status, "resolution_note": t.resolution_note,
        "created_at": utc_iso(t.created_at),
    } for t, f, v, c, b, barber in rows]


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


def message_rows(db: Session, user: dict, limit: int = 10) -> list[dict]:
    query = db.query(MessageLog, Visit, Customer).join(
        Visit, Visit.id == MessageLog.visit_id
    ).join(Customer, Customer.id == Visit.customer_id)
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    return [{
        "id": m.id, "visit_id": v.id, "customer_name": c.name, "status": m.status,
        "message": m.message, "created_at": utc_iso(m.created_at), "channel": "whatsapp_mock",
    } for m, v, c in query.order_by(MessageLog.created_at.desc()).limit(limit).all()]


def visit_snapshot(db: Session, visit: Visit) -> dict:
    return visit_json(db, visit)


def audit_logs_initial(db: Session, user: dict) -> list[dict]:
    query = db.query(AuditLog)
    if user["role"] == "barber":
        ids = db.query(Visit.id).filter(Visit.barber_id == user["barber_id"]).subquery()
        query = query.filter(or_(
            AuditLog.actor_user_id == user["id"],
            and_(AuditLog.entity_type == "visit", AuditLog.entity_id.in_(ids)),
        ))
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(20).all()
    return [{
        "id": r.id, "actor_username": r.actor_username, "actor_role": r.actor_role,
        "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
        "change_note": r.change_note, "created_at": utc_iso(r.created_at),
    } for r in rows]


@app.get("/api/service-catalog")
def get_service_catalog(user: dict = Depends(get_current_user)):
    return SERVICE_CATALOG


@app.get("/api/branches")
def get_branches(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return branch_rows(db, user)


@app.get("/api/barbers")
def get_barbers(branch_id: Optional[int] = None, db: Session = Depends(get_db),
                user: dict = Depends(get_current_user)):
    rows = barber_rows(db, user)
    return [b for b in rows if not branch_id or b["branch_id"] == branch_id]


@app.get("/api/customers/search")
def search_customers(q: str = Query(min_length=1, max_length=120), db: Session = Depends(get_db),
                     user: dict = Depends(get_current_user)):
    term, digits = q.strip(), normalize_phone(q.strip())
    matches = []
    for customer in customer_rows(db, user):
        name_match = term.casefold() in customer["name"].casefold()
        phone_digits = normalize_phone(customer["phone"])
        phone_match = bool(digits) and (phone_digits == digits or (len(digits) >= 3 and digits in phone_digits))
        if name_match or phone_match:
            matches.append(customer)
    if digits:
        matches.sort(key=lambda c: normalize_phone(c["phone"]) != digits)
    return matches[:10]


@app.get("/api/customers")
def get_customers(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return customer_rows(db, user)


@app.get("/api/customers/{customer_id}/reviews")
def get_customer_review_history(customer_id: int, db: Session = Depends(get_db),
                                user: dict = Depends(get_current_user)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    query = db.query(Visit, Branch, Barber, Feedback).join(
        Branch, Branch.id == Visit.branch_id
    ).join(Barber, Barber.id == Visit.barber_id).outerjoin(
        Feedback, Feedback.visit_id == Visit.id
    ).filter(Visit.customer_id == customer_id)
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(Visit.completed_at.desc(), Visit.id.desc()).all()
    # Do not reveal a customer record to a barber unless they have served that customer.
    if user["role"] == "barber" and not rows:
        raise HTTPException(status_code=404, detail="Customer not found in your visit history.")

    visit_count = len(rows)
    reviews = []
    for index, (visit, branch, barber, feedback) in enumerate(rows):
        if not feedback:
            continue
        reviews.append({
            "id": feedback.id,
            "visit_id": visit.id,
            "visit_number": visit_count - index,
            "completed_at": utc_iso(visit.completed_at),
            "service_name": visit.service_name,
            "amount": visit.amount,
            "branch_name": branch.name,
            "barber_name": barber.name,
            "rating": feedback.rating,
            "comment": feedback.comment or "",
            "created_at": utc_iso(feedback.created_at),
        })

    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone or "",
            "location": customer.location or "",
        },
        "visit_count": visit_count,
        "review_count": len(reviews),
        "reviews": reviews,
    }


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return dashboard_data(db, user)


@app.get("/api/visits")
def get_visits(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db),
               user: dict = Depends(get_current_user)):
    return visit_rows(db, user, limit)


@app.get("/api/visits/{visit_id}/history")
def get_visit_history(visit_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, detail="Visit not found.")
    check_visit_access(visit, user)
    rows = db.query(AuditLog).filter_by(entity_type="visit", entity_id=visit_id).order_by(
        AuditLog.created_at.desc(), AuditLog.id.desc()
    ).limit(100).all()
    return [{
        "id": r.id, "actor_username": r.actor_username, "actor_role": r.actor_role,
        "action": r.action, "before_data": r.before_data, "after_data": r.after_data,
        "change_note": r.change_note, "created_at": utc_iso(r.created_at),
    } for r in rows]


@app.patch("/api/visits/{visit_id}")
def update_visit(visit_id: int, payload: VisitUpdate, db: Session = Depends(get_db),
                 user: dict = Depends(get_current_user)):
    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, detail="Visit not found.")
    check_visit_access(visit, user)
    check_latest_visit_editable(db, visit)
    before = visit_snapshot(db, visit)
    if payload.customer_id is not None:
        if payload.customer_id != visit.customer_id:
            raise HTTPException(
                status_code=400,
                detail="A visit cannot be reassigned to another customer during editing. Create a new visit for a different customer.",
            )
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(404, detail="Customer not found.")
        if user["role"] == "barber":
            ids = {x[0] for x in db.query(Visit.customer_id).filter(
                Visit.branch_id == branch_id_for_user(db, user)
            ).distinct().all()}
            if customer.id not in ids:
                raise HTTPException(403, detail="Customer is not in your branch's records.")
        visit.customer_id = customer.id
    if user["role"] == "owner":
        if payload.branch_id is not None:
            if not db.get(Branch, payload.branch_id):
                raise HTTPException(404, detail="Branch not found.")
            visit.branch_id = payload.branch_id
        if payload.barber_id is not None:
            barber = db.get(Barber, payload.barber_id)
            if not barber:
                raise HTTPException(404, detail="Barber not found.")
            if barber.branch_id != visit.branch_id:
                raise HTTPException(400, detail="Selected barber must belong to the visit branch.")
            visit.barber_id = barber.id
    elif payload.branch_id is not None and payload.branch_id != visit.branch_id:
        raise HTTPException(403, detail="Barbers cannot move visits between branches.")
    if payload.completed_at is not None:
        stamp = payload.completed_at
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        visit.completed_at = stamp.astimezone(timezone.utc).replace(tzinfo=None)
    if payload.messaging_consent is not None:
        visit.feedback_requested = payload.messaging_consent
    if payload.services is not None:
        if not payload.services:
            raise HTTPException(400, detail="A visit must contain at least one service.")
        visit.service_name = " + ".join(
            f"{line.service_name} ×{line.quantity}" if line.quantity > 1 else line.service_name
            for line in payload.services
        )
        visit.amount = round(sum(line.quantity * line.unit_price for line in payload.services), 2)
        db.query(VisitService).filter_by(visit_id=visit.id).delete(synchronize_session=False)
        db.flush()
        for line in payload.services:
            db.add(VisitService(
                visit_id=visit.id, service_name=line.service_name, quantity=line.quantity,
                unit_price=line.unit_price, line_total=round(line.quantity * line.unit_price, 2),
            ))
    visit.updated_by_user_id = user["id"]
    db.flush()
    after = visit_snapshot(db, visit)
    add_audit(db, user, "visit.update", "visit", visit.id, before, after, payload.change_note)
    db.commit()
    db.refresh(visit)
    return {"visit": visit_snapshot(db, visit)}


@app.post("/api/visits", status_code=201)
def create_visit(payload: VisitCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    if user["role"] == "barber":
        assigned = db.get(Barber, user["barber_id"])
        if not assigned:
            raise HTTPException(403, detail="This account is not assigned to a barber.")
        if payload.branch_id != assigned.branch_id:
            raise HTTPException(403, detail="You can only record visits at your assigned branch.")
        branch_id, barber_id = assigned.branch_id, assigned.id
    else:
        branch_id, barber_id = payload.branch_id, payload.barber_id
    branch, barber = db.get(Branch, branch_id), db.get(Barber, barber_id)
    if not branch or not barber:
        raise HTTPException(404, detail="Branch or barber not found.")
    if barber.branch_id != branch.id:
        raise HTTPException(400, detail="Barber does not belong to the selected branch.")
    if payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(404, detail="Customer not found. Search again and select a customer.")
        if user["role"] == "barber":
            # Returning-customer lookup is private to visits assigned to the signed-in barber.
            ids = {x[0] for x in db.query(Visit.customer_id).filter(
                Visit.barber_id == user["barber_id"]
            ).distinct().all()}
            if customer.id not in ids:
                raise HTTPException(403, detail="You can only select customers from your own visit history.")
    else:
        name, phone, location = (payload.customer_name or "").strip(), (payload.customer_phone or "").strip(), (payload.customer_location or "").strip()
        normalized_phone = normalize_phone(phone)
        if len(normalized_phone) < 7 or len(normalized_phone) > 15:
            raise HTTPException(400, detail="Enter a valid customer phone number (7–15 digits).")
        if not name:
            raise HTTPException(400, detail="Customer name is required for a new customer.")
        for existing in db.query(Customer).all():
            if normalize_phone(existing.phone) and normalize_phone(existing.phone) == normalized_phone:
                raise HTTPException(409, detail="This phone number is already registered. Search for the existing customer.")
        customer = Customer(name=name, phone=phone, location=location, created_by_user_id=user["id"])
        db.add(customer)
        db.flush()
    lines = payload.services or (
        [VisitServiceInput(service_name=payload.service_name, quantity=1, unit_price=payload.amount)]
        if payload.service_name and payload.amount is not None else []
    )
    if not lines:
        raise HTTPException(400, detail="Add at least one service.")
    amount = round(sum(line.quantity * line.unit_price for line in lines), 2)
    summary = " + ".join(f"{line.service_name} ×{line.quantity}" if line.quantity > 1 else line.service_name for line in lines)
    if payload.messaging_consent:
        customer.messaging_consent = True
    stamp = payload.completed_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc).replace(tzinfo=None)
    visit = Visit(
        customer_id=customer.id, branch_id=branch.id, barber_id=barber.id, service_name=summary,
        amount=amount, completed_at=stamp, feedback_requested=payload.messaging_consent,
        created_by_user_id=user["id"], updated_by_user_id=user["id"],
    )
    db.add(visit)
    db.flush()
    for line in lines:
        db.add(VisitService(visit_id=visit.id, service_name=line.service_name,
            quantity=line.quantity, unit_price=line.unit_price,
            line_total=round(line.quantity * line.unit_price, 2)))
    if payload.messaging_consent:
        db.add(MessageLog(visit_id=visit.id, status="mock_queued", message=message_for(customer.name)))
    db.flush()
    add_audit(db, user, "visit.create", "visit", visit.id, None, visit_snapshot(db, visit), "Visit created")
    db.commit()
    db.refresh(visit)
    return {"visit": visit_snapshot(db, visit),
            "message_status": "mock_queued" if payload.messaging_consent else "not_requested",
            "notice": "Demo only: no real WhatsApp message was sent."}


@app.get("/api/feedback")
def get_feedback(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db),
                 user: dict = Depends(require_owner)):
    return feedback_rows(db, user, limit)


@app.post("/api/feedback", status_code=201)
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


@app.get("/api/recovery-tasks")
def get_tasks(status: Optional[str] = None, limit: int = Query(default=20, ge=1, le=100),
              db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    rows = task_rows(db, user, limit)
    if status:
        if status not in {"open", "in_progress", "resolved"}:
            raise HTTPException(400, detail="Invalid status.")
        rows = [r for r in rows if r["status"] == status]
    return rows


@app.patch("/api/recovery-tasks/{task_id}")
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


@app.get("/api/insights")
def get_insights(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return insight_data(db, user)


@app.get("/api/messages")
def get_messages(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db),
                 user: dict = Depends(get_current_user)):
    return message_rows(db, user, limit)


@app.get("/api/notifications")
def get_notifications(limit: int = Query(default=50, ge=1, le=100),
                      db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Show feedback received on visits visible to this account; never expose audit events here."""
    query = db.query(Feedback, Visit, Customer, Branch, Barber).join(
        Visit, Visit.id == Feedback.visit_id
    ).join(Customer, Customer.id == Visit.customer_id).join(
        Branch, Branch.id == Visit.branch_id
    ).join(Barber, Barber.id == Visit.barber_id)
    if user["role"] == "barber":
        query = query.filter(Visit.barber_id == user["barber_id"])
    rows = query.order_by(Feedback.created_at.desc(), Feedback.id.desc()).limit(limit).all()
    visit_sequences: dict[int, tuple[int, int]] = {}
    history_rows = db.query(Visit.id, Visit.customer_id).order_by(
        Visit.completed_at.desc(), Visit.id.desc()
    ).all()
    per_customer: dict[int, list[int]] = {}
    for history_visit_id, customer_id in history_rows:
        per_customer.setdefault(customer_id, []).append(history_visit_id)
    for ids in per_customer.values():
        for index, history_visit_id in enumerate(ids):
            visit_sequences[history_visit_id] = (len(ids) - index, len(ids))

    notifications = []
    for feedback, visit, customer, branch, barber in rows:
        number, total = visit_sequences.get(visit.id, (1, 1))
        notifications.append({
            "id": "feedback-" + str(feedback.id),
            "type": "customer_feedback",
            "title": "Customer feedback received",
            "message": (feedback.comment or "").strip(),
            "customer_id": customer.id,
            "customer_name": customer.name,
            "visit_id": visit.id,
            "visit_number": number,
            "visit_count": total,
            "rating": feedback.rating,
            "service_name": visit.service_name,
            "amount": visit.amount,
            "branch_name": branch.name,
            "barber_name": barber.name,
            "created_at": utc_iso(feedback.created_at),
            "completed_at": utc_iso(visit.completed_at),
            "is_read": False,
        })
    return {
        "notifications": notifications,
        "count": len(notifications),
    }


@app.get("/api/audit-logs")
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


@app.get("/api/customer-ratings")
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


@app.post("/api/customer-ratings", status_code=201)
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


@app.get("/api/staff-users")
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


@app.post("/api/demo/reset")
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


@app.get("/api/bootstrap")
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
