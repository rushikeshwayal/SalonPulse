"""Response contracts for the owner home overview."""

from pydantic import BaseModel


class HomeSummary(BaseModel):
    total_visits: int
    revenue: float
    feedback_count: int
    low_feedback_count: int
    open_recovery_tasks: int
    average_rating: float | None
    feedback_response_rate: float
    repeat_customer_rate: float
    branches: int
    barbers: int
