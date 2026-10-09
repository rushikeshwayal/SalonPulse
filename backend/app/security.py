"""Password hashing, bearer-token creation and token verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from .config import AUTH_SECRET, PBKDF2_ITERATIONS, TOKEN_TTL_SECONDS
from .database import SessionLocal
from .models import Barber, StaffUser


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(18)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${b64url(salt)}${b64url(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = b64url_decode(salt_text)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(b64url(candidate), expected)
    except (ValueError, TypeError):
        return False


def user_public(user: StaffUser) -> dict:
    barber = None
    if user.barber_id:
        with SessionLocal() as db:
            barber = db.get(Barber, user.barber_id)
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "display_name": user.display_name, "role": user.role, "barber_id": user.barber_id,
        "branch_id": barber.branch_id if barber else None,
        "is_active": user.is_active, "must_change_password": user.must_change_password,
    }


def create_access_token(user: StaffUser) -> str:
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64url(json.dumps({
        "sub": str(user.id), "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "iat": int(time.time()), "nonce": secrets.token_urlsafe(8),
    }, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode()
    signature = hmac.new(AUTH_SECRET.encode(), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{b64url(signature)}"


def verify_access_token(token: str) -> Optional[dict]:
    try:
        header_text, payload_text, signature_text = token.split(".")
        header = json.loads(b64url_decode(header_text))
        if header.get("alg") != "HS256":
            return None
        message = f"{header_text}.{payload_text}".encode()
        expected = b64url(hmac.new(AUTH_SECRET.encode(), message, hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature_text):
            return None
        payload = json.loads(b64url_decode(payload_text))
        if int(payload.get("exp", 0)) <= int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def actor_view(user: StaffUser) -> dict:
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "display_name": user.display_name, "role": user.role,
        "barber_id": user.barber_id, "must_change_password": user.must_change_password,
    }
