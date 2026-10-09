"""Shared Pydantic contracts grouped by domain."""

from .auth import LoginRequest, ChangePasswordRequest
from .visits import VisitServiceInput, VisitCreate, VisitUpdate
from .feedback import FeedbackCreate, RecoveryUpdate
from .ratings import CustomerRatingCreate

__all__ = [
    "LoginRequest", "ChangePasswordRequest", "VisitServiceInput", "VisitCreate",
    "VisitUpdate", "FeedbackCreate", "RecoveryUpdate", "CustomerRatingCreate",
]
