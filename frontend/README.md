# Multi-Agent Opinion Simulation Platform — Frontend

**Week 5 of the Qubeterra AI NextGen Program (N-Labs AI Fellowship)**

This is the user-facing Next.js application for a multi-agent AI debate platform. It streams live discussion events from a FastAPI backend, renders agent messages as they arrive, and presents quantitative analytics (opinion trajectories, agreement, influence, sentiment) once a discussion completes.

---

## Quick Start

### Prerequisites

- Node.js 20+
- A running FastAPI backend (see `../../backend/`) **or** `MOCK_BACKEND=true` for development without a backend

### Development

```bash
cd frontend/simu-discuss

# Copy environment template
cp .env.example .env.local
# Edit .env.local — set FASTAPI_INTERNAL_URL if backend is running

# Install dependencies
npm install

# Start dev server
npm run dev
# Open http://localhost:3000
```

### Mock backend mode (no FastAPI required)

```bash
# In .env.local:
MOCK_BACKEND=true

npm run dev
```

This serves static persona fixtures and streams a canned 2-agent discussion sequence. Analytics use a pre-built mock payload. All UI flows are testable without a running backend.

---

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Start development server (hot reload) |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run typecheck` | TypeScript type check (must pass with zero errors) |
| `npm run lint` | ESLint via next lint (must pass with zero warnings) |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FASTAPI_INTERNAL_URL` | `http://localhost:8000` | Backend URL (server-side only, never exposed to browser) |
| `NEXT_PUBLIC_APP_NAME` | `Multi-Agent Opinion Simulator` | App title shown in browser tab |
| `MOCK_BACKEND` | `false` | When `true`, all API routes return static fixtures |

Copy `.env.example` to `.env.local` for development. **Never commit `.env.local`.**

---

## Architecture

```
Browser
  └── Next.js (port 3000)
        ├── /api/* route handlers   <- proxy layer (server-side only)
        └── UI pages
              └── FastAPI (port 8000, internal Docker network only)
```

The browser never calls FastAPI directly. All backend calls go through `/api/*` route handlers, keeping the `FASTAPI_INTERNAL_URL` out of the browser.

---

## Route Map

| Route | Type | Purpose |
|---|---|---|
| `/` | Server | Home page — hero, pipeline, agent preview |
| `/discussions` | Client | Run / History / Personas tabs |
| `/discussions/[id]` | Client | Live discussion stream or transcript replay |
| `/analytics` | Server | Redirects to latest completed discussion |
| `/analytics/[discussionId]` | Client | Dashboard + Report tabs |
| `/api/health` | Route Handler | Aggregate health check |
| `/api/personas` | Route Handler | Persona list (proxy + mock fallback) |
| `/api/discussions` | Route Handler | Discussion history (proxy + mock fallback) |
| `/api/discussions/[id]` | Route Handler | Single discussion transcript |
| `/api/week3/discuss` | Route Handler | SSE pass-through (or mock stream) |
| `/api/week4/analytics/[id]` | Route Handler | Analytics JSON with 24h cache |
| `/api/week4/analytics/[id]/stream` | Route Handler | Analytics SSE (or synthetic from JSON) |
| `/api/week4/report/[id]` | Route Handler | Markdown report proxy |
| `/api/week4/visuals/[id]/[name]` | Route Handler | PNG visual proxy |

---

## Project Structure

```
app/                    Next.js App Router pages + API routes
components/             Shared UI components
  analytics/            MetricCard, ChartFrame, DataTable
  discussion/           ChatView, ChatMessage, ParticipantList, EvidencePanel, BriefPanel
  layout/               TopNav, Footer, StatusPill
  personas/             PersonaCard, PersonaModal
  ui/                   Button, Tabs, Skeleton, Toast, ErrorState
hooks/                  Client-side hooks (useStreamingDiscussion, useAnalyticsStream, ...)
lib/                    Pure utilities (sse, palette, log, env, format)
  mocks/                Static fixtures for MOCK_BACKEND=true
types/                  All TypeScript interfaces
docs/                   LOGGING_SPEC.md (for backend owner)
```

---

## Docker Compatibility

This app is built with `output: "standalone"` in `next.config.ts`. The teammate owning Task 4 (containerization) should use a multi-stage Dockerfile with:

```dockerfile
FROM node:20-alpine AS base
# ...build stage...
FROM node:20-alpine AS runner
COPY --from=base /app/.next/standalone ./
COPY --from=base /app/.next/static ./.next/static
COPY --from=base /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

The app expects `FASTAPI_INTERNAL_URL=http://fastapi:8000` inside the Docker network.

---

## Reviewer Reproduction

To reproduce the full flow:

1. Start the backend: `cd backend && docker compose up fastapi`
2. Start the frontend: `cd frontend/simu-discuss && npm run dev`
3. Open `http://localhost:3000`
4. Navigate to **Discussions -> Run**
5. Select a suggested brief, leave all 4 agents selected, click **Start Discussion**
6. Watch messages stream in real time
7. On completion, click **View Analytics**
8. All 5 metric cards should populate progressively

To test without a backend:
```bash
MOCK_BACKEND=true npm run dev
```

---

## Limitations

- **No authentication.** Explicitly out of scope for Week 5.
- **In-memory analytics cache.** The 24h cache in `/api/week4/analytics/[id]/route.ts` is process-local. Multi-replica deployments will not share cache. Replace with Redis for production.
- **Analytics SSE endpoint not yet on backend.** The frontend falls back to polling `GET /week4/analytics/{id}` and synthesizes metric events. Once the backend implements the SSE endpoint, the fallback is bypassed automatically.
- **Token-level streaming not implemented.** The backend does not emit `turn_started` / `token` events yet. The frontend renders complete turns on `turn_completed`.

---

## Open Questions (Backend — Youssef)

See `docs/LOGGING_SPEC.md` for the full logging contract.

Backend questions still pending (from the brief section 19):

1. Does `participant_ids: null` default to all personas in `personas.json`?
2. Does the backend cap `topic` length below 4000 characters?
3. Can `GET /week4/analytics/{id}/stream` be implemented as an SSE endpoint?
4. What is the exact shape of `GET /health/ready`?

---

## Tech Stack

| Layer | Package | Version |
|---|---|---|
| Framework | Next.js | 16.3.6 |
| Language | TypeScript | 5.x (strict) |
| Styling | Tailwind CSS | 4.x |
| Charts | Recharts | 3.x |
| Markdown | react-markdown + remark-gfm | 10.x + 4.x |
| Icons | lucide-react | 1.47 |
| Utilities | clsx | 2.x |
