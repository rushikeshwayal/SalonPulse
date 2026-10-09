"""Customer review-history response contracts."""

from typing import Any
from pydantic import BaseModel, Field

class CustomerProfile(BaseModel):
    id: int
    name: str
    phone: str = ""
    location: str = ""

class CustomerReviewHistory(BaseModel):
    customer: CustomerProfile
    visit_count: int
    review_count: int
    reviews: list[dict[str, Any]] = Field(default_factory=list)
