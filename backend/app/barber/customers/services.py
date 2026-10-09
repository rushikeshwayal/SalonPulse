"""Owner customer search and visit-linked review history."""

from sqlalchemy.orm import Session
from ...services import customer_rows, normalize_phone
from ...routers.customers import get_customer_review_history


def list_customers(db: Session, user: dict):
    return customer_rows(db, user)


def search_customers(db: Session, user: dict, q: str):
    term, digits = q.strip(), normalize_phone(q.strip())
    matches = []
    for customer in customer_rows(db, user):
        name_match = term.casefold() in customer["name"].casefold()
        phone_digits = normalize_phone(customer["phone"])
        phone_match = bool(digits) and (phone_digits == digits or (len(digits) >= 3 and digits in phone_digits))
        if name_match or phone_match:
            matches.append(customer)
    if digits:
        matches.sort(key=lambda customer: normalize_phone(customer["phone"]) != digits)
    return matches[:10]

def customer_reviews(db: Session, user: dict, customer_id: int):
    return get_customer_review_history(customer_id=customer_id, db=db, user=user)
