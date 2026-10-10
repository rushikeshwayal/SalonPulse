# SalonPulse — Next.js frontend

This is the main React UI for SalonPulse, built with Next.js App Router, TypeScript and Tailwind CSS 4. The FastAPI backend remains the source of truth for authentication, permissions, visit version history, customer feedback, notifications and owner reports.

## Run locally

Requires Node.js 20.9+ and npm.

\`\`\`powershell
cd frontend/my-project
npm install
npm run dev
\`\`\`

Open http://localhost:3000. Requests to \`/api/*\` are proxied through Next.js to the existing FastAPI deployment. To use a different backend URL, set \`SALONPULSE_API_ORIGIN\` in the environment before starting the app.

## Structure

- \`app/\`: sign-in and role-specific App Router pages.
- \`components/\`: shared workspace frame, dashboard, customer directory, visit timeline/editor, notifications and management pages.
- \`lib/\`: API client, formatting helpers and TypeScript response contracts.
- \`components/icons.tsx\`: small shared SVG icon set, no extra icon dependency needed.

## Security and data behavior

- The API validates tokens and role permissions; client-side navigation is not the security boundary.
- Visit edits use the existing version/audit API; older visits remain read-only.
- Barber customer lookup/notifications are restricted by the backend.
- Messaging remains mock-only. This prototype does not send WhatsApp messages.
