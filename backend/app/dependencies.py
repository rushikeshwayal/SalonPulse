"""FastAPI dependencies for the current user and owner-only operations."""

from fastapi import Depends, HTTPException, Request


def get_current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


def require_owner(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner access required.")
    return user
