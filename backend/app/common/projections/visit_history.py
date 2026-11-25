"""Shared per-customer visit sequence across the complete visit history."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Visit


def visit_sequence_by_id(db: Session) -> dict[int, tuple[int, int, bool]]:
    """Map visit ID to (visit number, customer visit count, is latest visit).

    Sequence across all visits, independent of the caller's role or page limit.
    """
    history_rows = db.query(Visit.id, Visit.customer_id).order_by(
        Visit.completed_at.desc(), Visit.id.desc()
    ).all()
    per_customer: dict[int, list[int]] = {}
    for visit_id, customer_id in history_rows:
        per_customer.setdefault(customer_id, []).append(visit_id)

    sequences: dict[int, tuple[int, int, bool]] = {}
    for visit_ids in per_customer.values():
        total = len(visit_ids)
        for index, visit_id in enumerate(visit_ids):
            sequences[visit_id] = (total - index, total, index == 0)
    return sequences
