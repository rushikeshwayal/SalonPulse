"""Owner finance calculations and branch/barber financial aggregates."""

from sqlalchemy.orm import Session

from ...services import dashboard_data, insight_data


def finance_overview(db: Session, user: dict) -> dict:
    summary = dashboard_data(db, user)
    insights = insight_data(db, user)
    revenue = float(summary.get("revenue") or 0)
    visits = int(summary.get("total_visits") or 0)
    return {
        "total_revenue": round(revenue, 2),
        "total_visits": visits,
        "average_ticket_value": round(revenue / visits, 2) if visits else 0,
        "branches": insights.get("branches", []),
        "barbers": insights.get("barbers", []),
    }
