# SalonPulse

SalonPulse is a runnable demo for collecting salon feedback, monitoring customer experience, and tracking follow-up tasks. It uses **Python + FastAPI**, **SQLAlchemy**, and **SQLite**, with a lightweight static frontend served by FastAPI.

## Features

- Dashboard with visits, average rating, and open recovery tasks
- Seeded demo branches, barbers, customers, visits and feedback
- Low feedback scores automatically create a recovery task
- Manage recovery task status
- Branch and barber insights
- Mock message log (does not send real WhatsApp messages)
- Interactive API documentation at `/docs`
- Tests and a GitHub Actions workflow

## Run locally

Requires Python 3.10+.

### Windows PowerShell

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### macOS / Linux

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- Frontend: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health

SQLite database is created locally under `backend/` on first run. Demo rows are seeded when the database is empty.

## Main API routes

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/branches`
- `GET /api/barbers`
- `GET /api/customers`
- `GET /api/visits`
- `POST /api/visits`
- `GET /api/feedback`
- `POST /api/feedback`
- `GET /api/recovery-tasks`
- `PATCH /api/recovery-tasks/{task_id}`
- `GET /api/insights`
- `GET /api/messages`
- `POST /api/demo/reset`

## Supabase PostgreSQL and Vercel

The repository is configured for Vercel's Python runtime through `api/index.py` and `vercel.json`. When the `DATABASE_URL` environment variable is set, the app uses PostgreSQL through Psycopg; without it, local development uses SQLite. On Vercel, `DATABASE_URL` is required so ephemeral filesystem storage is never used as the production database.

1. In Supabase, open the active project and choose **Connect**.
2. Copy the **Transaction pooler** connection string. Keep the password private; don't commit it or paste it into source files.
3. In Vercel Project Settings → Environment Variables, add `DATABASE_URL` for Production, Preview, and Development. Use the connection string as a sensitive secret.
4. Redeploy after saving the variable.

The current schema migration is tracked in `supabase/migrations/`. Tables have Row Level Security enabled and no access granted to the public `anon` or `authenticated` roles. The FastAPI application connects server-side using the database connection string; keep this backend private until authentication and authorization are implemented.

## Tests

From `backend/`, install requirements, then run `pytest -q`.

## Important limitations

This is a local demo with fictional seeded data. The message log is mocked; it does not contact WhatsApp or another provider. Before production, add authentication and authorization, migrations, environment-based configuration, rate limiting, structured logging, privacy/retention policies, and real provider integration with user consent.