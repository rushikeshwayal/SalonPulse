"""Common system endpoints, shared across both panels."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ...config import FRONTEND_DIR

router = APIRouter(tags=["Common / System"])


@router.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@router.get("/api/health", summary="Health check")
def health():
    return {"status": "ok", "app": "SalonPulse API", "messaging": "mock_only"}
