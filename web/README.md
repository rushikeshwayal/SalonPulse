# SalonPulse Next.js frontend

This directory contains the React/Next.js frontend. The existing FastAPI backend and legacy HTML frontend remain unchanged while this implementation is validated.

## Local development

Requires Node.js 20.9+ and npm.

    cd web
    npm install
    npm run dev

The frontend uses the current FastAPI deployment through the rewrite in next.config.ts. The bearer token remains in sessionStorage for compatibility with the existing authentication flow. No backend credentials are bundled in the browser.

## Structure

- app/: routes and workspace layout
- components/: shared shell, customer list, visit editor, timeline and management views
- lib/: API client, display helpers and shared response types

The existing frontend/ directory is intentionally retained until the new UI passes role, workflow, and deployment testing.
