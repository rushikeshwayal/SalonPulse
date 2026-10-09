"""SalonPulse FastAPI application factory and ASGI entry point.

Domain logic, persistence, authentication and HTTP routes live in focused modules.
Keep this file as a small composition root so existing ASGI entry points stay stable.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import model definitions before SQLite create_all runs so metadata is complete.
from . import models as _models  # noqa: F401
from .config import DATABASE_URL, FRONTEND_DIR
from .database import Base, SessionLocal, engine, get_db
from .middleware import install_auth_middleware
from .models import (
    AuditLog, Barber, Branch, Customer, CustomerRating, Feedback, MessageLog,
    RecoveryTask, StaffUser, Visit, VisitService,
)
from .security import hash_password
from .seed import seed
from .routers import auth, catalog, customers, management, notifications, system, visits

app = FastAPI(
    title="SalonPulse API",
    version="0.1.0",
    description="Salon feedback and service recovery demo. Messaging is mock-only.",
)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
install_auth_middleware(app)

for route_module in (auth, system, catalog, customers, visits, notifications, management):
    app.include_router(route_module.router)


@app.on_event("startup")
def startup() -> None:
    # Local SQLite is self-contained, so create/seed its demo schema on startup.
    # Production Postgres is managed by checked-in Supabase migrations; avoid schema
    # introspection and demo-seed queries on every serverless cold start.
    if DATABASE_URL.startswith("sqlite:"):
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed(db)
