"""Compatibility exports for request schemas grouped by domain under app.common.schemas."""

from .common.schemas import (
    ChangePasswordRequest, CustomerRatingCreate, FeedbackCreate, LoginRequest,
    RecoveryUpdate, VisitCreate, VisitServiceInput, VisitUpdate,
)

__all__ = [
    "ChangePasswordRequest", "CustomerRatingCreate", "FeedbackCreate", "LoginRequest",
    "RecoveryUpdate", "VisitCreate", "VisitServiceInput", "VisitUpdate",
]
