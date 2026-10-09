"""Owner staff account and branch-assignment query."""

from sqlalchemy.orm import Session
from ...models import Barber, Branch, StaffUser


def list_staff(db: Session, user: dict) -> list[dict]:
    staff_rows = db.query(StaffUser).order_by(StaffUser.role, StaffUser.display_name).all()
    barbers = {barber.id: barber for barber in db.query(Barber).all()}
    branches = {branch.id: branch for branch in db.query(Branch).all()}
    return [{
        "id": staff.id, "username": staff.username, "email": staff.email,
        "display_name": staff.display_name, "role": staff.role, "barber_id": staff.barber_id,
        "branch_name": branches.get(barbers[staff.barber_id].branch_id).name
            if staff.barber_id in barbers and barbers[staff.barber_id].branch_id in branches else "",
        "is_active": staff.is_active, "must_change_password": staff.must_change_password,
    } for staff in staff_rows]
