"""Public root and health-check endpoints."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..config import FRONTEND_DIR

router = APIRouter()


@router.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND / "index.html")


@router.get("/api/health")
def health():
    return {"status": "ok", "app": "SalonPulse API", "messaging": "mock_only"}
