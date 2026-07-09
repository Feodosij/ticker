# FinAlly E2E Tests

Playwright end-to-end tests that exercise the full stack (FastAPI + static
Next.js frontend + market simulator + mock LLM) against the real production
container.

## Run in Docker (recommended, matches CI)

From the repo root:

```bash
docker compose -f test/docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from playwright
```

This builds the production image, starts it with `LLM_MOCK=true` and no
`MASSIVE_API_KEY` (deterministic mock LLM + market simulator), and runs the
Playwright suite from a separate browser container. Tear down with:

```bash
docker compose -f test/docker-compose.test.yml down
```

## Run locally against a running app

Start the app (fresh DB) on :8000, then:

```bash
cd test
npm install
npx playwright install chromium
BASE_URL=http://localhost:8000 npx playwright test
```

## Scenarios (PLAN.md §12)

1. `01-fresh-start` — default 10-ticker watchlist, $10k cash, live price ticks
2. `02-watchlist` — add a ticker (it ticks), then remove it
3. `03-buy` — buy shares; cash drops, position appears, portfolio updates
4. `04-sell` — sell shares; cash rises, fully-sold position disappears
5. `05-portfolio-viz` — heatmap colored by P&L sign, P&L chart has data
6. `06-chat` — mocked AI "buy" executes a trade shown inline and in the portfolio
7. `07-sse-resilience` — connected → blocked stream → recovers

Tests run serially (`workers: 1`) because the backend is single-user global
state; they share one server.
