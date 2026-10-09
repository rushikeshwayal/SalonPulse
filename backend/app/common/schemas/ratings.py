"""CustomerRatingCreate request schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CustomerRatingCreate(BaseModel):
    visit_id: int
    rating: int = Field(ge=1, le=5)
    note: str = Field(default="", max_length=1000)
