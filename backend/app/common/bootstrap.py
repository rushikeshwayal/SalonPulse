"""Shared bootstrap projection used by owner and barber home pages."""

from sqlalchemy.orm import Session

from ..constants import SERVICE_CATALOG
from .projections.audit import audit_logs_initial
from .projections.catalog import barber_rows, branch_rows
from .projections.customers import customer_rows
from .projections.dashboard import dashboard_data, insight_data
from .projections.feedback import feedback_rows
from .projections.messages import message_rows
from .projections.recovery import task_rows
from .projections.visits import visit_rows


def build_bootstrap(db: Session, user: dict) -> dict:
    """Keep the legacy bootstrap response shape while applying role visibility."""
    is_owner = user["role"] == "owner"
    return {
        "user": user,
        "dashboard": dashboard_data(db, user),
        "branches": branch_rows(db, user),
        "barbers": barber_rows(db, user),
        "customers": customer_rows(db, user),
        "visits": visit_rows(db, user, 20),
        "feedback": feedback_rows(db, user, 20) if is_owner else [],
        "tasks": task_rows(db, user, 20) if is_owner else [],
        "insights": insight_data(db, user),
        "messages": message_rows(db, user, 10) if is_owner else [],
        "serviceCatalog": SERVICE_CATALOG,
        "auditLogs": audit_logs_initial(db, user) if is_owner else [],
    }
