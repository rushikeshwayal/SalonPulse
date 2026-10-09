"""Owner staff-account directory service."""

from sqlalchemy.orm import Session
from ...routers.management import get_staff_users as _get_staff_users

def list_staff(db: Session, user: dict): return _get_staff_users(db=db, user=user)
