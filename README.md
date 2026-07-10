# Ticker

AI-powered trading workstation — live market data, a simulated portfolio, and an LLM co-pilot that can analyze your positions and place trades on your behalf. Looks and feels like a Bloomberg-style terminal; runs entirely on your machine in one Docker container.

Course capstone project, built by a team of coding agents. See [`planning/PLAN.md`](planning/PLAN.md) for the full product spec and [`planning/MARKET_DATA_DESIGN.md`](planning/MARKET_DATA_DESIGN.md) for the market-data subsystem design.

## Features

- Live-updating watchlist with flash animations and per-ticker sparklines, streamed over SSE
- Simulated market data (geometric Brownian motion) by default, or real quotes via the Massive (Polygon.io) API
- $10,000 virtual cash, market-order buy/sell with instant fill, no fees
- Portfolio heatmap (treemap by weight/P&L), P&L history chart, positions table
- AI chat copilot — ask about your portfolio, get analysis, and let it execute trades and manage your watchlist for you
- Single container, single port, SQLite storage — no external services required to run

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (static export) + TypeScript, Tailwind CSS, Recharts |
| Backend | FastAPI (Python), served by Uvicorn, managed with `uv` |
| Database | SQLite, lazily initialized and seeded on first run |
| Real-time data | Server-Sent Events (`EventSource`) |
| AI / LLM | [LiteLLM](https://www.litellm.ai/) → OpenRouter, structured outputs |
| Testing | Pytest (backend), Vitest + React Testing Library (frontend), Playwright (E2E) |
| Packaging | Multi-stage Docker build (Node → Python), Docker Compose |

## Project structure

```
ticker/
├── frontend/     # Next.js app (static export)
├── backend/      # FastAPI app (uv project) — API routes, DB layer, market data, LLM chat
├── planning/     # Product spec and design docs
├── test/         # Playwright E2E suite + docker-compose.test.yml
├── scripts/      # start/stop scripts (macOS/Linux + Windows)
├── db/           # Runtime volume mount — finally.db lives here (gitignored)
├── Dockerfile
└── docker-compose.yml
```

## Prerequisites

- [Docker](https://www.docker.com/) (Desktop or Engine) with Compose
- An [OpenRouter](https://openrouter.ai/keys) API key for the AI chat (optional if you only want live prices/trading — see below)

## Quick start

1. Copy the environment file and add your key:

   ```bash
   cp .env.example .env
   # edit .env and set OPENROUTER_API_KEY
   ```

2. Build and run:

   ```bash
   ./scripts/start_mac.sh          # macOS/Linux
   # or
   ./scripts/start_windows.ps1     # Windows PowerShell
   ```

   Or with Docker Compose directly:

   ```bash
   docker compose up --build
   ```

3. Open **http://localhost:8000**.

To stop:

```bash
./scripts/stop_mac.sh       # or stop_windows.ps1
# or
docker compose down
```

Your portfolio and trade history persist in `./db/finally.db` across restarts (it's a bind-mounted volume) — `stop_*` scripts and `docker compose down` never touch it.

## Environment variables

| Variable | Required | Effect |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes, for AI chat | Powers the LLM chat assistant. Not needed if `LLM_MOCK=true`. |
| `MASSIVE_API_KEY` | No | Set → real market data via the Massive (Polygon.io) REST API. Empty/unset → built-in GBM simulator (default, recommended). Read once at startup. |
| `LLM_MOCK` | No | `true` → deterministic, keyword-matched chat responses instead of calling OpenRouter (fast, free, used by E2E tests). Default `false`. |

## Running without Docker (development)

**Backend:**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev     # dev server at :3000 — UI only, API calls will 404 (no proxy configured)
```

The frontend calls `/api/*` as same-origin requests, which only resolve when FastAPI is actually serving the built frontend (see below) — `next dev` alone is useful for UI iteration but won't have live data. To exercise the full app locally without Docker:

```bash
cd frontend && npm run build          # writes the static export to frontend/out/
rm -rf backend/static && cp -r frontend/out backend/static
cd backend && uv run uvicorn app.main:app --port 8000
```

Then open http://localhost:8000. Re-run the two build/copy steps after frontend changes.

## Testing

```bash
# Backend unit tests
cd backend && uv run pytest && uv run ruff check .

# Frontend unit/component tests
cd frontend && npm test

# End-to-end (Playwright, full stack in Docker, LLM_MOCK=true)
docker compose -f test/docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from playwright
```

See [`test/README.md`](test/README.md) for E2E scenario details and how to run Playwright against a locally running instance instead of Docker.
