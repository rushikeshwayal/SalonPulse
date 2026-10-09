"""Local/demo data seeding. Production tables are managed by migrations."""

from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import (
    AuditLog, Barber, Branch, Customer, CustomerRating, Feedback, MessageLog,
    RecoveryTask, StaffUser, Visit, VisitService,
)
from .services import message_for
def seed_demo_users(db: Session) -> None:
    seeds = [
        ("owner", "owner@salonpulse.demo", "SalonPulse Owner", "owner", None,
         "pbkdf2_sha256$420000$23iYiCHmItKShez99fmXmWPU$5OIytF91x0M09r_5_-HPzAaFUpr53TIDCoJZ4auk8W0"),
        ("aarav", "aarav.patil@salonpulse.demo", "Aarav Patil", "barber", 1,
         "pbkdf2_sha256$420000$Qaxp9eRhlRvi95K0pwEIOerl$6dtYYrJLsRMuyckc0QrZUw2uVbDNHXiYQgZIodmylDw"),
        ("rohan", "rohan.jadhav@salonpulse.demo", "Rohan Jadhav", "barber", 2,
         "pbkdf2_sha256$420000$4CGHxqs1t5TvPNezMXpOxWrV$otoUciAgH-RfsFidVrHA6yl4U7VwekLUxfAfTsYYSCU"),
        ("kabir", "kabir.shah@salonpulse.demo", "Kabir Shah", "barber", 3,
         "pbkdf2_sha256$420000$s-1scbpsXi1XGG97_YYf8iOw$TbVmDvb1Jv6ecXjqiauQHhP51w8axIB-JP9X7w2ToII"),
        ("dev", "dev.kulkarni@salonpulse.demo", "Dev Kulkarni", "barber", 4,
         "pbkdf2_sha256$420000$sU6ogeeSBNbNNuBcv1k4ncb7$SzGgO-3Iyq0BG_ao6Y8DZV5BUDOUyamWlWDjZlkoUbs"),
        ("ishaan", "ishaan.more@salonpulse.demo", "Ishaan More", "barber", 5,
         "pbkdf2_sha256$420000$CtK1t4WZEPW3-WIIudz8sZjZ$9qwhrAFtPRqzAzcgtSLLCnf2tjvtZJmfx0_3E3IiXNM"),
        ("arjun", "arjun.deshmukh@salonpulse.demo", "Arjun Deshmukh", "barber", 6,
         "pbkdf2_sha256$420000$M1u_l-lwKUC3Nnc5wn7o4G-s$ibaVw8SeZKJVk51D7h8vXmC33IfJTplRKTpLRK5Mx9c"),
    ]
    for username, email, display_name, role, barber_id, password_hash_value in seeds:
        exists = db.query(StaffUser.id).filter(
            or_(StaffUser.username == username, StaffUser.email == email)
        ).first()
        if not exists:
            db.add(StaffUser(
                username=username, email=email, display_name=display_name, role=role,
                barber_id=barber_id, password_hash=password_hash_value,
                is_active=True, must_change_password=True,
            ))
    db.commit()


def seed(db: Session, reset: bool = False):
    if reset:
        # Delete demo rows in FK-safe order. Never drop/recreate production tables,
        # which would discard database grants and Row Level Security settings.
        for model in (AuditLog, CustomerRating, MessageLog, RecoveryTask, Feedback, VisitService, Visit, Customer):
            db.query(model).delete(synchronize_session=False)
        db.commit()
    if db.query(Customer).count() and db.query(Visit).count():
        seed_demo_users(db)
        return

    branches = db.query(Branch).order_by(Branch.id).all()
    if not branches:
        branches = [
            Branch(name="The Gentlemen's Club — Koregaon Park", location="Pune"),
            Branch(name="The Gentlemen's Club — Viman Nagar", location="Pune"),
            Branch(name="The Gentlemen's Club — Baner", location="Pune"),
            Branch(name="The Gentlemen's Club — Kalyani Nagar", location="Pune"),
        ]
        db.add_all(branches)
        db.flush()

    barbers = db.query(Barber).order_by(Barber.id).all()
    if not barbers:
        barbers = [
            Barber(branch_id=branches[0].id, name="Aarav Patil"),
            Barber(branch_id=branches[0].id, name="Rohan Jadhav"),
            Barber(branch_id=branches[1].id, name="Kabir Shah"),
            Barber(branch_id=branches[1].id, name="Dev Kulkarni"),
            Barber(branch_id=branches[2].id, name="Ishaan More"),
            Barber(branch_id=branches[3].id, name="Arjun Deshmukh"),
        ]
        db.add_all(barbers)
        db.flush()
    customers = [
        # Seed customers are fictional; keep phone fields empty instead of using fake,
        # potentially callable numbers. Real customer details are entered in the form.
        Customer(name="Aditya Shah", phone="", location="Viman Nagar", messaging_consent=True),
        Customer(name="Neel Joshi", phone="", location="Kalyani Nagar", messaging_consent=True),
        Customer(name="Samir Desai", phone="", location="Koregaon Park", messaging_consent=True),
        Customer(name="Riya Demo", phone="", location="Kharadi", messaging_consent=True),
        Customer(name="Vikram Rao", phone="", location="Wagholi", messaging_consent=False),
        Customer(name="Kunal Mehta", phone="", location="Baner", messaging_consent=True),
    ]
    db.add_all(barbers + customers)
    db.flush()

    now = datetime.utcnow()
    samples = [
        (0, 0, 0, "Haircut + beard", 500, 1, 4, "Great experience. Asked for the same fade next time."),
        (1, 0, 1, "Haircut", 300, 3, 2, "The sides were uneven and I felt rushed."),
        (2, 1, 2, "Haircut", 350, 5, 5, "Very happy with the cut."),
        (3, 1, 3, "Haircut + wash", 450, 7, 3, "Waiting time was longer than expected."),
        (4, 2, 4, "Haircut", 300, 9, None, ""),
        (5, 0, 0, "Haircut", 300, 12, 1, "The shape was not what I requested."),
        (0, 1, 3, "Haircut", 300, 15, None, ""),
    ]
    for ci, bi, barber_index, service, amount, days, rating, comment in samples:
        v = Visit(
            customer_id=customers[ci].id, branch_id=branches[bi].id, barber_id=barbers[barber_index].id,
            service_name=service, amount=amount, completed_at=now - timedelta(days=days),
            feedback_requested=True,
        )
        db.add(v)
        db.flush()
        db.add(VisitService(
            visit_id=v.id, service_name=service, quantity=1,
            unit_price=float(amount), line_total=float(amount),
        ))
        db.add(MessageLog(
            visit_id=v.id,
            status="mock_sent" if customers[ci].messaging_consent else "skipped_no_consent",
            message=message_for(customers[ci].name),
        ))
        if rating is not None:
            f = Feedback(
                visit_id=v.id, rating=rating, comment=comment,
                created_at=v.completed_at + timedelta(minutes=10),
            )
            db.add(f)
            db.flush()
            if rating <= 2:
                db.add(RecoveryTask(feedback_id=f.id, status="in_progress" if rating == 2 else "open"))
    db.commit()
    seed_demo_users(db)
