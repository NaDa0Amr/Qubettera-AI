# Qubettera frontend

Next.js UI for evidence-based AI discussions, transcript history, and analytics.
The browser uses Next.js API routes, which forward requests to the shared
[FastAPI backend](../backend/README.md).

## Local development

From the repository root, with Node.js 20.9+ and the backend dependencies installed:

```powershell
npm --prefix frontend ci
Copy-Item frontend/.env.example frontend/.env.local
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
npm --prefix frontend run dev
```

Open http://localhost:3000. See the [root README](../README.md) for Python,
PostgreSQL, model, and retrieval setup.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `FASTAPI_INTERNAL_URL` | `http://localhost:8000` | Server-side backend address |
| `MOCK_BACKEND` | `false` | Explicit frontend demo mode with canned fixtures |
| `NEXT_PUBLIC_APP_NAME` | `Qubettera` | Navigation and browser title; set before building |

Use `frontend/.env.local` for local overrides. With mock mode disabled, failed
persona/history requests return an error instead of displaying demo data.
The home page remains available when the backend is offline.

Frontend mock mode differs from **fake discussion mode**: fake discussions use
the real backend orchestrator and save history without requiring a model or DB.
Analytics requires a live discussion; it rejects fake opinions.

## Checks and production build

```powershell
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test:smoke
```

The build produces standalone server output for the multi-stage Dockerfile.
From the project root, start the full stack using:

```powershell
docker compose --profile web up --build -d
```

Compose sets `FASTAPI_INTERNAL_URL=http://backend:8000` and disables mock mode.
The root `.env` configures the backend. Public app-name overrides must be passed
as a frontend Docker build argument (`NEXT_PUBLIC_APP_NAME`). Google fonts are
self-hosted by Next.js after being downloaded during the build.

The stack binds web ports to localhost. Remote hosting requires an authenticated
reverse proxy, long request timeouts, and disabled SSE buffering. Run one API
worker because analytics task deduplication is process-local.

## Pages

| Route | Purpose |
| --- | --- |
| `/` | Introduction and available personas |
| `/discussions` | Run, History, and Personas tabs |
| `/discussions/[id]` | Live discussion or saved transcript |
| `/analytics` | Latest saved analytics, or an empty/error state |
| `/analytics/[discussionId]` | Metrics, report, and visuals |

Shared components live in `components/`, streaming hooks in `hooks/`, API types
in `types/`, and server-side collection access in `lib/backend.ts`.
