"""Environment-based configuration and application paths.

Production-only requirements remain strict: Vercel must supply DATABASE_URL and
APP_AUTH_SECRET. Local development defaults to a file-backed SQLite database.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPOSITORY_DIR = BACKEND_DIR.parent
SQLITE_DATABASE_PATH = BACKEND_DIR / "salonpulse.db"

_FRONTEND_CANDIDATES = (
    REPOSITORY_DIR / "frontend",
    Path.cwd() / "frontend",
    BACKEND_DIR / "frontend",
)
FRONTEND_DIR = next(
    (candidate for candidate in _FRONTEND_CANDIDATES if (candidate / "index.html").is_file()),
    _FRONTEND_CANDIDATES[0],
)


def resolve_database_url() -> str:
    """Resolve the server-side database URL, requiring PostgreSQL on Vercel."""
    configured = os.getenv("DATABASE_URL")
    if configured:
        if configured.startswith("postgres://"):
            configured = configured.replace("postgres://", "postgresql+psycopg://", 1)
        elif configured.startswith("postgresql://"):
            configured = configured.replace("postgresql://", "postgresql+psycopg://", 1)
        if configured.startswith("postgresql+psycopg://") and "sslmode=" not in configured:
            configured += ("&" if "?" in configured else "?") + "sslmode=require"
        return configured

    if os.getenv("VERCEL") == "1":
        raise RuntimeError(
            "DATABASE_URL is required on Vercel. Set it to the Supabase PostgreSQL connection string."
        )
    return f"sqlite:///{SQLITE_DATABASE_PATH}"


DATABASE_URL = resolve_database_url()

AUTH_SECRET = os.getenv("APP_AUTH_SECRET")
if os.getenv("VERCEL") == "1" and not AUTH_SECRET:
    raise RuntimeError("APP_AUTH_SECRET must be configured for production authentication.")
AUTH_SECRET = AUTH_SECRET or "local-development-only-not-for-production"

TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", str(8 * 60 * 60)))
PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "420000"))

