"""VisitServiceInput and VisitCreate and VisitUpdate request schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


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

class VisitUpdate(BaseModel):
    branch_id: Optional[int] = None
    barber_id: Optional[int] = None
    customer_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    services: Optional[list[VisitServiceInput]] = Field(default=None, max_length=10)
    messaging_consent: Optional[bool] = None
    change_note: str = Field(default="", max_length=500)
