"""Backward-compatible exports for shared domain projections.

New code should import from app.common.projections or app.common.services.
This facade remains so legacy routes and tests can migrate independently.
"""

from .common.projections.access import (
    branch_id_for_user, check_latest_visit_editable, check_visit_access,
    latest_customer_visit_id, visible_customers_query,
)
from .common.projections.audit import add_audit, audit_logs_initial
from .common.projections.catalog import barber_rows, branch_rows
from .common.projections.customers import customer_rows
from .common.projections.dashboard import dashboard_data, insight_data
from .common.projections.feedback import feedback_rows
from .common.projections.formatting import message_for, normalize_phone, utc_iso
from .common.projections.messages import message_rows
from .common.projections.recovery import task_rows
from .common.projections.serializers import (
    customer_json, feedback_json, task_json, visit_json, visit_snapshot,
)
from .common.projections.visits import visit_rows

__all__ = [
    "add_audit", "audit_logs_initial", "barber_rows", "branch_id_for_user",
    "branch_rows", "check_latest_visit_editable", "check_visit_access",
    "customer_json", "customer_rows", "dashboard_data", "feedback_json",
    "feedback_rows", "insight_data", "latest_customer_visit_id", "message_for",
    "message_rows", "normalize_phone", "task_json", "task_rows", "utc_iso",
    "visit_json", "visit_rows", "visit_snapshot", "visible_customers_query",
]
