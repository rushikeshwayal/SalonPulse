"""SalonPulse application composition root.

Shared infrastructure is initialized here. Owner and barber feature routers are
mounted independently so authentication, APIs and OpenAPI docs remain organized
by panel. Legacy routes remain available but are hidden from OpenAPI during the
compatibility period.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

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
from .common.auth.route import router as auth_router
from .common.system.route import router as system_router
from .owner.home.route import router as owner_home_router
from .owner.finance.route import router as owner_finance_router
from .owner.catalog.route import router as owner_catalog_router
from .owner.customers.route import router as owner_customers_router
from .owner.visits.route import router as owner_visits_router
from .owner.feedback.route import router as owner_feedback_router
from .owner.recovery.route import router as owner_recovery_router
from .owner.insights.route import router as owner_insights_router
from .owner.messages.route import router as owner_messages_router
from .owner.audit.route import router as owner_audit_router
from .owner.staff.route import router as owner_staff_router
from .owner.ratings.route import router as owner_ratings_router
from .owner.demo.route import router as owner_demo_router
from .barber.home.route import router as barber_home_router
from .barber.catalog.route import router as barber_catalog_router
from .barber.customers.route import router as barber_customers_router
from .barber.visits.route import router as barber_visits_router
from .barber.notifications.route import router as barber_notifications_router
from .barber.ratings.route import router as barber_ratings_router
from .routers import catalog as legacy_catalog
from .routers import customers as legacy_customers
from .routers import management as legacy_management
from .routers import notifications as legacy_notifications
from .routers import visits as legacy_visits

OPENAPI_TAGS = [
    {"name": "Common / Authentication", "description": "Sign-in, session identity and password management shared by both panels."},
    {"name": "Common / System", "description": "Health checks and app-level endpoints."},
    {"name": "Owner / Home", "description": "Owner dashboard and owner workspace bootstrap data."},
    {"name": "Owner / Finance", "description": "Revenue totals, average ticket and financial breakdowns."},
    {"name": "Owner / Reference Data", "description": "Owner-side branches, staff and service catalogue."},
    {"name": "Owner / Customers", "description": "Owner-wide customer directory and review history."},
    {"name": "Owner / Visits", "description": "Create, inspect and edit customer visits across branches."},
    {"name": "Owner / Feedback", "description": "Customer feedback inbox and management feedback operations."},
    {"name": "Owner / Recovery", "description": "Customer service recovery queue."},
    {"name": "Owner / Insights", "description": "Branch and employee performance analytics."},
    {"name": "Owner / Messaging", "description": "Mock outbound message activity; messages are not actually delivered."},
    {"name": "Owner / Audit", "description": "Internal audit history restricted to owner accounts."},
    {"name": "Owner / Staff", "description": "Staff accounts and assignments."},
    {"name": "Owner / Customer Ratings", "description": "Business-wide customer interaction ratings recorded by staff."},
    {"name": "Owner / Demo Tools", "description": "Local fictional demo tools; disabled for production data."},
    {"name": "Barber / Home", "description": "Personal barber summary and barber workspace bootstrap."},
    {"name": "Barber / Reference Data", "description": "Assigned barber reference data and service catalogue."},
    {"name": "Barber / Customers", "description": "Customer list limited to customers this barber personally served."},
    {"name": "Barber / Visits", "description": "Record and manage eligible visits assigned to this barber."},
    {"name": "Barber / Notifications", "description": "Feedback notifications linked to visits served by this barber."},
    {"name": "Barber / Customer Ratings", "description": "Visit-specific customer interaction ratings."},
]

app = FastAPI(
    title="SalonPulse API",
    version="0.2.0",
    description="Salon operations API with separate owner and barber panels. Messaging is mock-only.",
    openapi_tags=OPENAPI_TAGS,
)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
install_auth_middleware(app)

# Shared APIs
app.include_router(auth_router)
app.include_router(system_router)

# Canonical, documented panel APIs
for panel_router in (
    owner_home_router, owner_finance_router, owner_catalog_router, owner_customers_router,
    owner_visits_router, owner_feedback_router, owner_recovery_router, owner_insights_router,
    owner_messages_router, owner_audit_router, owner_staff_router, owner_ratings_router,
    owner_demo_router, barber_home_router, barber_catalog_router, barber_customers_router,
    barber_visits_router, barber_notifications_router, barber_ratings_router,
):
    app.include_router(panel_router)

# Compatibility routes preserve the former /api/* contract for scripts/integrations.
# The browser app now uses /api/owner/* and /api/barber/* paths; legacy entries are
# intentionally excluded from OpenAPI to avoid duplicate, role-ambiguous documentation.
for legacy_router in (legacy_catalog.router, legacy_customers.router, legacy_visits.router,
                      legacy_notifications.router, legacy_management.router):
    app.include_router(legacy_router, include_in_schema=False)


@app.on_event("startup")
def startup() -> None:
    # Local SQLite is self-contained, so create/seed its demo schema on startup.
    # Production Postgres is managed by checked-in Supabase migrations; avoid schema
    # introspection and demo-seed queries on every serverless cold start.
    if DATABASE_URL.startswith("sqlite:"):
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed(db)
