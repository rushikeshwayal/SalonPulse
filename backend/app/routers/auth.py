"""Authentication and account routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import StaffUser
from ..schemas import ChangePasswordRequest, LoginRequest
from ..security import (
    TOKEN_TTL_SECONDS, actor_view, create_access_token, hash_password, verify_password,
)
from ..services import add_audit

router = APIRouter()


@router.post("/api/auth/login")
def auth_login(payload: LoginRequest, db: Session = Depends(get_db)):
    identifier = payload.identifier.strip().casefold()
    user = db.query(StaffUser).filter(
        or_(func.lower(StaffUser.username) == identifier, func.lower(StaffUser.email) == identifier)
    ).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username/email or password.")
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": actor_view(user),
        "expires_in": TOKEN_TTL_SECONDS,
    }


@router.get("/api/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    return user


@router.post("/api/auth/change-password")
def auth_change_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    record = db.get(StaffUser, user["id"])
    if not record or not verify_password(payload.current_password, record.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="Choose a different new password.")
    before = {"must_change_password": record.must_change_password}
    record.password_hash = hash_password(payload.new_password)
    record.must_change_password = False
    record.updated_at = datetime.utcnow()
    add_audit(db, user, "credential.change", "staff_user", record.id, before,
              {"must_change_password": False}, "Password changed by account holder")
    db.commit()
    return {"status": "ok", "user": {**user, "must_change_password": False}}
