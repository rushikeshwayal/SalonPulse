"""Owner staff directory."""

from sqlalchemy.orm import Session
from ...common.services.staff import list_staff

def list_owner_staff(db: Session, user: dict): return list_staff(db, user)

def list_staff(db: Session, user: dict): return list_owner_staff(db, user)
