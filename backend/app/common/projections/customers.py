"""Customer directory projection with barber-specific served-customer scope."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models import Customer, Visit
from .access import visible_customers_query
from .formatting import utc_iso

def customer_rows(db: Session, user: dict) -> list[dict]:
    visits_query = db.query(
        Visit.customer_id, func.count(Visit.id).label("visit_count"),
        func.max(Visit.completed_at).label("last_visit"),
    )
    if user["role"] == "barber":
        visits_query = visits_query.filter(Visit.barber_id == user["barber_id"])
    stats = visits_query.group_by(Visit.customer_id).all()
    stats_map = {row.customer_id: row for row in stats}
    result = []
    for c in visible_customers_query(db, user).order_by(Customer.name).all():
        row = stats_map.get(c.id)
        result.append({
            "id": c.id, "name": c.name, "phone": c.phone, "location": c.location or "",
            "messaging_consent": c.messaging_consent,
            "visit_count": int(row.visit_count) if row else 0,
            "last_visit": utc_iso(row.last_visit) if row else None,
        })
    return result
