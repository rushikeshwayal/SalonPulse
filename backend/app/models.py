"""Compatibility exports for shared domain ORM models.

The actual table declarations are grouped by domain under app.common.models.
Import from this module to keep existing app/tests and API modules compatible.
"""

from .common.models import (
    AuditLog, Barber, Branch, Customer, CustomerRating, Feedback,
    MessageLog, RecoveryTask, StaffUser, Visit, VisitService,
)

__all__ = [
    "AuditLog", "Barber", "Branch", "Customer", "CustomerRating", "Feedback",
    "MessageLog", "RecoveryTask", "StaffUser", "Visit", "VisitService",
]
