# SalonPulse

SalonPulse is a salon operations demo built with **FastAPI**, **SQLAlchemy**, **Pydantic**, **Supabase PostgreSQL/SQLite**, and a static mobile-friendly frontend. The API supports authenticated owner/barber workspaces, service visits, visit version history, customer feedback, barber-specific notifications and owner reporting. Messaging is mock-only; it does not send WhatsApp messages.

## Features

- Owner and barber sign-in with role-based API authorization
- Multi-branch, customer, barber and visit management
- Customer visit timelines, multi-service line items and totals
- Latest-visit-only editing with before/after audit snapshots
- Customer feedback tied to its visit and barber-scoped notifications
- Owner-only reporting, recovery tasks, staff listing and audit logs
- Supabase PostgreSQL in production; local SQLite for development
- Interactive API documentation at `/docs`
- API tests and JavaScript syntax checks in GitHub Actions

## Backend layout

The backend uses a small **composition root** in `backend/app/main.py`; it assembles the FastAPI app and registers routers. Domain code is split by responsibility:

```text
backend/
  app/
    main.py             # Create the FastAPI app, mount static files, include routers
    config.py           # Environment settings and repository/frontend paths
    constants.py        # Service catalogue and application constants
    database.py         # SQLAlchemy engine, Base, SessionLocal and get_db
    models.py           # ORM models and database table mappings
    schemas.py          # Pydantic request/validation schemas
    security.py         # Password hashes and signed bearer tokens
    middleware.py       # Authentication middleware
    dependencies.py     # Current-user and owner-only dependencies
    services.py         # Query helpers, domain operations and response serializers
    seed.py             # Local/demo data seed logic
    routers/
      auth.py           # Login, current account and password update
      system.py         # Root page and health check
      catalog.py        # Branches, barbers and service catalogue
      customers.py      # Customer search and visit-linked review history
      visits.py         # Dashboard and visit creation/update/history
      notifications.py  # Feedback notifications
      management.py     # Reporting, recovery, staff and owner audit endpoints
  tests/
    test_api.py
  .env.example          # Local environment template
  requirements.txt
```

Keep request/response contracts in `schemas.py`, database entities in `models.py`, and SQLAlchemy session/configuration in `database.py`. Route modules must depend on those modules and shared services, **not import from `main.py`**. The `main.py` module continues to expose commonly used objects such as `app`, `SessionLocal`, and ORM models for the existing test and Vercel entry points.

## Run locally

Requires Python 3.10+.

### Windows PowerShell

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --env-file .env
```

### macOS / Linux

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --env-file .env
```

Open the frontend at http://127.0.0.1:8000, API docs at http://127.0.0.1:8000/docs, and health check at http://127.0.0.1:8000/api/health. With `DATABASE_URL=` left blank, SQLite is created under `backend/salonpulse.db` and seeded locally. Demo reset is intentionally disabled on the persistent PostgreSQL database.

## Environment configuration

- `DATABASE_URL`: leave blank for local SQLite; Vercel requires a Supabase PostgreSQL connection URL. Prefer the transaction pooler for serverless deployments.
- `APP_AUTH_SECRET`: local-only sample value in `.env.example`; set a long, unique secret in Vercel Project Settings for production. Never commit a live secret.
- `TOKEN_TTL_SECONDS`: bearer-token lifetime; defaults to 8 hours.
- `PBKDF2_ITERATIONS`: password-hashing work factor; defaults to 420,000.

For production, configure `DATABASE_URL` and `APP_AUTH_SECRET` in Vercel's environment variables, then redeploy. Schema changes are applied using the checked-in migrations under `supabase/migrations/`; the serverless startup deliberately does not call `create_all()` or seed PostgreSQL tables.

## Tests

From the repository root:

```bash
cd backend
python -m pytest -q
node --check ../frontend/app.js
```

## Important limitations

This is still a demo using fictional seed data. WhatsApp delivery is not implemented, notifications are generated from recorded customer feedback, and there is no external production identity provider, password-reset flow, rate limiting, or formal data-retention policy. Review those requirements before handling real customer data at scale.
