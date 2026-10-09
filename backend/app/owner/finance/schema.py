"""Response contracts for financial overview endpoints."""

from typing import Any
from pydantic import BaseModel, Field


class FinanceOverview(BaseModel):
    total_revenue: float
    total_visits: int
    average_ticket_value: float
    branches: list[dict[str, Any]] = Field(default_factory=list)
    barbers: list[dict[str, Any]] = Field(default_factory=list)
