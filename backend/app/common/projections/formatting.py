"""Date/time, phone normalization and message formatting helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Optional

def normalize_phone(value: str | None) -> str:
    digits = re.sub("[^0-9]", "", value or "")
    # Treat Indian 10-digit numbers and +91-prefixed numbers as the same phone.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits

def utc_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def message_for(name: str) -> str:
    first = (name or "there").split()[0]
    return (
        f"Hi {first}, thanks for visiting us today. We'd appreciate your honest feedback "
        "about your experience. Your feedback is shared with salon management so we can improve. "
        "Reply with a rating from 1 to 5. You can opt out of future messages at any time."
    )
