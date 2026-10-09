"""Authentication middleware for protected API and documentation routes."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .database import SessionLocal
from .models import StaffUser
from .security import actor_view, verify_access_token


def install_auth_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def require_login(request: Request, call_next):
        path = request.url.path
        if (
            path == "/" or path == "/api/health" or path == "/api/auth/login"
            or path.startswith("/static/") or request.method == "OPTIONS"
        ):
            return await call_next(request)
        if not path.startswith("/api/") and path not in {"/docs", "/redoc", "/openapi.json"}:
            return await call_next(request)
        auth_header = request.headers.get("authorization", "")
        token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
        claims = verify_access_token(token) if token else None
        if not claims:
            return JSONResponse(status_code=401, content={"detail": "Please sign in to continue."},
                                headers={"WWW-Authenticate": "Bearer"})
        try:
            user_id = int(claims.get("sub", "0"))
        except (ValueError, TypeError):
            user_id = 0
        with SessionLocal() as db:
            user = db.get(StaffUser, user_id)
            if not user or not user.is_active:
                return JSONResponse(status_code=401, content={"detail": "This account is not active."})
            if user.must_change_password and path not in {"/api/auth/me", "/api/auth/change-password"}:
                return JSONResponse(status_code=403, content={"detail": "PASSWORD_CHANGE_REQUIRED: Update your temporary password first."})
            request.state.user = actor_view(user)
        return await call_next(request)
    
