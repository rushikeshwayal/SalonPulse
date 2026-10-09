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

The backend is organized into **shared infrastructure**, **common domain services and projections**, and two explicit API panels. Each panel feature has a thin `route.py`, feature-specific `schema.py` where it needs request/response contracts, and a `services.py` layer. Read models, serializers, access rules and formatting helpers live under `common/projections/`. Shared entities are defined once because both panels work with the same visit/customer tables; root `app.services` is now a compatibility re-export rather than a large implementation file.

```text
backend/app/
  main.py                    # App composition; register common and panel routers
  config.py                  # Environment configuration and paths
  database.py                # SQLAlchemy engine, Base, sessions, get_db
  dependencies.py             # Signed-in user, owner and barber access checks
  middleware.py              # Authentication middleware
  security.py                # Password hashing and bearer tokens
  seed.py                    # Local fictional demo seed data
  common/
    auth/route.py             # Shared login, /me and password change
    system/route.py           # Health and frontend route
    bootstrap.py              # Role-safe initial workspace payload
    models/                   # Shared ORM entities, grouped by domain
      organization.py
      staff.py
      customer.py
      visit.py
      visit_service.py
      feedback.py
      recovery.py
      messaging.py
      audit.py
      rating.py
    schemas/                  # Shared Pydantic request contracts by domain
      auth.py
      visits.py
      feedback.py
      ratings.py
    services/                 # Domain use-cases shared across panels
      projections/               # Shared read models, serializers and access rules
        access.py
        audit.py
        catalog.py
        customers.py
        dashboard.py
        feedback.py
        formatting.py
        messages.py
        recovery.py
        serializers.py
        visits.py
      visits.py
      customers.py
      feedback.py
      recovery.py
      ratings.py
      audit.py
      notifications.py
      messages.py
      insights.py
      staff.py
      demo.py
  owner/
    home/                     # Dashboard and bootstrap payload
    finance/                  # Revenue/ticket and store/employee totals
    catalog/                  # Branches, barbers, services
    customers/                 # Business-wide customer history
    visits/                    # Visit CRUD and version history
    feedback/                  # Feedback inbox
    recovery/                  # Customer recovery tasks
    insights/                  # Store/employee performance
    messages/                  # Mock message activity
    audit/                     # Internal audit history
    staff/                     # Staff accounts
    ratings/                   # Business-wide interaction ratings
    demo/                      # Local-only demo reset
  barber/
    home/                      # Personal dashboard and bootstrap
    catalog/                   # Assigned branch and services
    customers/                 # Only customers personally served
    visits/                    # Assigned visit workflows
    notifications/             # Feedback on own visits
    ratings/                  # Interaction rating entry and history
  routers/                     # Backward-compatible /api/* routes, hidden in OpenAPI
  tests/test_api.py
```

### API organization

- **Common:** `/api/auth/*` and `/api/health`
- **Owner:** `/api/owner/home`, `/api/owner/finance`, `/api/owner/visits`, `/api/owner/customers`, `/api/owner/feedback`, `/api/owner/recovery-tasks`, `/api/owner/insights`, `/api/owner/audit-logs`, and related management routes.
- **Barber:** `/api/barber/home`, `/api/barber/visits`, `/api/barber/customers`, `/api/barber/notifications`, and `/api/barber/customer-ratings`.

Swagger/OpenAPI at `/docs` groups routes using panel-and-feature tags such as **Owner / Finance** and **Barber / Visits**. Role dependencies are checked on the server. Existing `/api/*` URLs are retained as hidden compatibility routes while the browser client uses the panel-specific endpoints. This allows older clients/tests to keep working without duplicating ambiguous entries in the API documentation.

Keep database entities shared rather than duplicating a `Visit` or `Customer` model under both panels. Home and finance are projections, not separate database tables, so their response schemas and service functions live in the feature packages without artificial ORM models.

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
