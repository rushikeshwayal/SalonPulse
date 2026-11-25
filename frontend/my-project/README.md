# SalonPulse frontend

The production UI is the Next.js application in this directory. The FastAPI service remains the source of truth for authentication, authorization, business rules and persistence.

## Run locally

Requirements: Node.js 20.9+ and npm.

```powershell
cd frontend/my-project
npm ci
Copy-Item .env.local.example .env.local
npm run dev
```

Open http://localhost:3000.

## Backend URL

Set one server-side environment variable in `.env.local`:

```dotenv
# Local FastAPI
SALONPULSE_API_ORIGIN=http://127.0.0.1:8000

# Or deployed FastAPI
# SALONPULSE_API_ORIGIN=https://salon-pulse-one.vercel.app
```

Next.js proxies browser requests from `/api/*` to this origin using `next.config.ts`. Frontend code should always call the relative `/api/...` path through `lib/api.ts`; do not hardcode deployment domains in components. Restart `npm run dev` after changing `.env.local`.

For Vercel, set `SALONPULSE_API_ORIGIN` in the `salon-pulse-next` project's Environment Variables for the relevant environments, then redeploy. This variable is server-side and must not use the `NEXT_PUBLIC_` prefix.

## Project structure

- `app/`: routes, layouts and global styles (Next.js App Router).
- `components/`: shared UI and workspace features.
- `lib/api.ts`: the single HTTP client and shared formatting helpers.
- `lib/types.ts`: API response and domain types.
- `next.config.ts`: backend proxy configuration.

Keep feature-specific UI close to its route when it is not reused. Put genuinely shared components in `components/`; avoid creating one-file folders or abstractions that only add indirection.

## Quality checks

```powershell
npm run lint
npm run build
```

Authentication and role permissions are enforced by FastAPI, not by hiding frontend navigation. Messaging is currently mock-only; no WhatsApp messages are delivered.
