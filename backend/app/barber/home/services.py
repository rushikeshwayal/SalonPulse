"""Barber home projection, scoped to the authenticated barber."""

from sqlalchemy.orm import Session
from ...common.bootstrap import build_bootstrap
from ...services import dashboard_data

def get_home_summary(db: Session, user: dict): return dashboard_data(db, user)
def get_bootstrap(db: Session, user: dict): return build_bootstrap(db, user)
