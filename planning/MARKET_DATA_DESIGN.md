# Market Data Backend — Design

Detailed design for the market data subsystem described in [PLAN.md §6](./PLAN.md#6-market-data). Covers the unified provider interface, the shared price cache, the GBM simulator, the Massive (Polygon.io) REST client, and how they feed the `/api/stream/prices` SSE endpoint.

This is a design reference for the Backend/Market Data agents, not a rigid mandate on file layout — the module boundaries below are a recommendation.

## 1. Goals

- One abstract interface; the simulator and Massive client are interchangeable implementations selected once at startup based on `MASSIVE_API_KEY`.
- A single shared in-memory cache is the only thing SSE reads from. Neither the simulator nor the Massive poller talks to SSE clients directly.
- The simulator must look alive and interesting on screen (visible up/down movement every ~500ms) without being a rigorous financial model — this is a demo, not a pricing engine.
- The Massive client must never exceed its rate limit regardless of watchlist size, and must degrade gracefully (stale cache, not a crash) on network or auth failures.
- Both implementations must react to watchlist changes (ticker added/removed) at runtime, not just at startup.

## 2. Architecture

```
                 ┌─────────────────────┐
watchlist CRUD → │  set_tickers(set)    │
routes           └──────────┬───────────┘
                             │
                    MarketDataProvider          (ABC — one of the two below)
                    ┌────────┴────────┐
                    │                 │
          SimulatorProvider     MassiveProvider
          (GBM, asyncio task,   (httpx polling,
           tick every 500ms)     tick every N sec)
                    │                 │
                    └────────┬────────┘
                             ▼
                       PriceCache
                (ticker → latest PriceUpdate)
                             │
                             ▼
                 GET /api/stream/prices (SSE)
                (reads cache every 500ms,
                 pushes to every connected client)
```

One background task (whichever provider is active) is the sole writer to `PriceCache`. The SSE endpoint and any number of connected browser tabs are readers only. This is what lets multiple SSE clients share one upstream data source, and is the hook PLAN.md §6 calls out for future multi-user support.

## 3. Unified interface

```python
# backend/app/market_data/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ChangeDirection = Literal["up", "down", "flat"]


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    open_price: float          # session/day reference price, for daily % change
    timestamp: datetime        # UTC

    @property
    def change_direction(self) -> ChangeDirection:
        if self.price > self.previous_price:
            return "up"
        if self.price < self.previous_price:
            return "down"
        return "flat"

    @property
    def change_pct(self) -> float:
        if self.open_price == 0:
            return 0.0
        return (self.price - self.open_price) / self.open_price * 100


class MarketDataProvider(ABC):
    """Either implementation writes into the PriceCache it is constructed with."""

    @abstractmethod
    async def start(self) -> None:
        """Begin the background update loop. Must not block."""

    @abstractmethod
    async def stop(self) -> None:
        """Cancel the background loop cleanly (used on app shutdown)."""

    @abstractmethod
    def set_tickers(self, tickers: set[str]) -> None:
        """Replace the full set of tickers this provider tracks.

        Called once at startup with the seeded watchlist, and again on every
        watchlist add/remove. Implementations must pick up new tickers on
        their next tick without a restart.
        """
```

`PriceUpdate.open_price` is the field PLAN.md's §6 cache description doesn't spell out explicitly but the frontend needs it: the watchlist panel shows a "daily change %" (§10), which requires a reference price distinct from the previous tick. For the simulator, `open_price` is the price at the moment the ticker started being simulated in this run. For Massive, it's the exchange's official day-open (falling back to previous close before the market opens). `previous_price` stays purely tick-to-tick, driving the flash-green/flash-red animation.

### Provider selection

```python
# backend/app/market_data/__init__.py
import os
from .base import MarketDataProvider
from .cache import PriceCache
from .simulator import SimulatorProvider
from .massive import MassiveProvider

def create_market_data_provider(cache: PriceCache) -> MarketDataProvider:
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveProvider(cache=cache, api_key=api_key)
    return SimulatorProvider(cache=cache)
```

Called once during FastAPI startup (`lifespan`), per PLAN.md §5: `MASSIVE_API_KEY` is read once at process start and a change requires a restart — there is deliberately no hot-swap logic.

## 4. Shared price cache

```python
# backend/app/market_data/cache.py
from .base import PriceUpdate

class PriceCache:
    """In-memory latest-price store. Single writer (the active provider),
    many readers (SSE connections). No locking: FastAPI's asyncio event loop
    is single-threaded and every method here is synchronous (no `await`
    between the read and the write), so there's no interleaving to guard
    against.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}

    def set(self, update: PriceUpdate) -> None:
        self._prices[update.ticker] = update

    def get(self, ticker: str) -> PriceUpdate | None:
        return self._prices.get(ticker)

    def get_many(self, tickers: set[str]) -> list[PriceUpdate]:
        return [self._prices[t] for t in tickers if t in self._prices]

    def all_tickers(self) -> set[str]:
        return set(self._prices)
```

`PriceCache` is instantiated once in `app.state` at startup and injected into both the provider and the SSE route. Removing a ticker from the watchlist does **not** delete it from the cache — the row simply stops being requested by `get_many()` once the watchlist route updates the tracked ticker set. This avoids a race where a removal and an in-flight provider tick could re-add a stale entry.

## 5. Simulator provider

### GBM model

Each ticker follows geometric Brownian motion:

```
S(t+dt) = S(t) · exp[(μ − σ²/2)·dt + σ·√dt·Z],   Z ~ N(0, 1)
```

```python
# backend/app/market_data/simulator.py
import asyncio
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone

from .base import MarketDataProvider, PriceUpdate
from .cache import PriceCache

TICK_INTERVAL_SECONDS = 0.5

# One real second is treated as this many simulated market-seconds. At 1x,
# annualized vol translates into per-tick moves far too small to see (a
# stock with 30% annual vol only moves ~0.01%/tick). This is a demo, so we
# run the clock fast enough that price changes are visibly flashing every
# tick without looking absurd. Tune freely — see §5 "Tuning" below.
TIME_ACCELERATION = 50
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # ~5,896,800


@dataclass
class TickerParams:
    seed_price: float
    mu: float      # annualized drift, e.g. 0.10 = 10%/yr
    sigma: float    # annualized volatility, e.g. 0.30 = 30%/yr


# Default watchlist (PLAN.md §7). Prices/params are illustrative, not live
# quotes — chosen to give each name a distinct personality on screen.
SEED_PARAMS: dict[str, TickerParams] = {
    "AAPL":  TickerParams(190.00, mu=0.10, sigma=0.28),
    "GOOGL": TickerParams(175.00, mu=0.09, sigma=0.30),
    "MSFT":  TickerParams(420.00, mu=0.10, sigma=0.26),
    "AMZN":  TickerParams(185.00, mu=0.11, sigma=0.32),
    "TSLA":  TickerParams(250.00, mu=0.05, sigma=0.55),
    "NVDA":  TickerParams(130.00, mu=0.15, sigma=0.50),
    "META":  TickerParams(500.00, mu=0.10, sigma=0.34),
    "JPM":   TickerParams(210.00, mu=0.07, sigma=0.22),
    "V":     TickerParams(275.00, mu=0.08, sigma=0.20),
    "NFLX":  TickerParams(680.00, mu=0.09, sigma=0.35),
}

# Fallback for tickers added at runtime that aren't in SEED_PARAMS (the
# simulator has no real quote to seed from). Mid-range price, market-ish vol.
DEFAULT_PARAMS = TickerParams(seed_price=100.00, mu=0.08, sigma=0.30)


def gbm_step(price: float, mu: float, sigma: float, dt_years: float, rng: random.Random) -> float:
    z = rng.gauss(0.0, 1.0)
    drift = (mu - 0.5 * sigma ** 2) * dt_years
    shock = sigma * math.sqrt(dt_years) * z
    return price * math.exp(drift + shock)


@dataclass
class _TickerState:
    price: float
    open_price: float
    params: TickerParams


class SimulatorProvider(MarketDataProvider):
    def __init__(self, cache: PriceCache, seed: int | None = None) -> None:
        self._cache = cache
        self._rng = random.Random(seed)
        self._state: dict[str, _TickerState] = {}
        self._task: asyncio.Task | None = None
        self._dt_years = (TICK_INTERVAL_SECONDS * TIME_ACCELERATION) / TRADING_SECONDS_PER_YEAR

    def set_tickers(self, tickers: set[str]) -> None:
        for ticker in tickers:
            if ticker not in self._state:
                params = SEED_PARAMS.get(ticker, DEFAULT_PARAMS)
                self._state[ticker] = _TickerState(
                    price=params.seed_price,
                    open_price=params.seed_price,
                    params=params,
                )
        for ticker in list(self._state):
            if ticker not in tickers:
                del self._state[ticker]

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            for ticker, state in self._state.items():
                new_price = gbm_step(state.price, state.params.mu, state.params.sigma, self._dt_years, self._rng)
                new_price = round(new_price, 2)
                self._cache.set(PriceUpdate(
                    ticker=ticker,
                    price=new_price,
                    previous_price=state.price,
                    open_price=state.open_price,
                    timestamp=now,
                ))
                state.price = new_price
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
```

### Tuning

`TIME_ACCELERATION = 50` gives a stock with `σ = 0.30` roughly a 0.06%–0.07% standard deviation move per 500ms tick — enough to trigger the flash animation almost every tick without prices swinging wildly minute to minute. `TSLA` (`σ = 0.55`) moves visibly more, `V` (`σ = 0.20`) visibly less — this variation is intentional and part of what makes the watchlist feel alive. If ticks look too calm or too jumpy in practice, adjust `TIME_ACCELERATION` (linear in variance, quadratic in visual "jumpiness" since it scales `√dt`) rather than touching individual `σ` values.

### Stretch enhancements (optional, skip for v1 per PLAN.md §6)

Two enhancements the simulator can grow into without changing its interface:

1. **Correlated moves** — replace the independent `Z` per ticker with `Z_i = β·Z_market + √(1−β²)·Z_i_idiosyncratic`, where `Z_market` is one shared standard normal draw per tick and `β` (e.g. 0.6 for tech names, 0.2 for JPM/V) controls how much each ticker follows the market factor.
2. **Event jumps** — each tick, with small probability (e.g. `p = 0.002`, ~once per ~7 min of wall-clock at the default tick rate) apply an extra one-off multiplicative jump of ±2–5% to a single random ticker, on top of its normal GBM step.

Both are additive to `gbm_step` and don't change `PriceUpdate`, `PriceCache`, or the interface — implement only if time remains after the core simulator, watchlist, and Massive client work.

## 6. Massive (Polygon.io) provider

Massive is Polygon.io's current product name. Confirmed from their public docs:

- Base URL: `https://api.massive.com`
- Auth: `apiKey` query parameter (`Authorization: Bearer <key>` header also supported; query param is simpler here) — [REST quickstart](https://massive.com/docs/rest/quickstart)
- Full-market snapshot endpoint, which accepts a **comma-separated list of tickers in one call** — this is what lets us fetch the entire watchlist in a single request regardless of its size: `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,TSLA,GOOG` — [snapshot docs](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot)
- Free tier: 5 requests/minute ([rate limit FAQ](https://massive.com/knowledge-base/article/what-is-the-request-limit-for-massives-restful-apis)) — verify against current docs before shipping, tiers/limits change.

Example response shape (per Massive's docs):

```json
{
  "status": "OK",
  "tickers": [
    {
      "ticker": "AAPL",
      "lastTrade": { "p": 190.42, "t": 1730000000000000000 },
      "day":     { "o": 189.10, "c": 190.42, "h": 191.00, "l": 188.75 },
      "prevDay": { "o": 187.00, "c": 189.00 },
      "updated": 1730000000000000000
    }
  ]
}
```

### Poll interval and batching

One request per poll cycle covers the whole watchlist (comma-separated `tickers` param), so request rate is independent of watchlist size. At the free tier's 5 req/min limit, anything ≥ 12s stays technically compliant; default to **15s** for a safety margin against clock jitter and the periodic startup validation call below. This is a module-level constant, easy to lower on a paid tier:

```python
DEFAULT_POLL_INTERVAL_SECONDS = 15.0
```

### Implementation

```python
# backend/app/market_data/massive.py
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from .base import MarketDataProvider, PriceUpdate
from .cache import PriceCache

logger = logging.getLogger(__name__)

BASE_URL = "https://api.massive.com"
SNAPSHOT_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"
DEFAULT_POLL_INTERVAL_SECONDS = 15.0


class MassiveProvider(MarketDataProvider):
    def __init__(self, cache: PriceCache, api_key: str, poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS) -> None:
        self._cache = cache
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None
        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)

    def set_tickers(self, tickers: set[str]) -> None:
        self._tickers = set(tickers)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        await self._client.aclose()

    async def _run(self) -> None:
        while True:
            if self._tickers:
                await self._poll_once()
            await asyncio.sleep(self._poll_interval)

    async def _poll_once(self) -> None:
        params = {"tickers": ",".join(sorted(self._tickers)), "apiKey": self._api_key}
        try:
            resp = await self._client.get(SNAPSHOT_PATH, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                logger.error("Massive API rejected the API key (HTTP %s) — check MASSIVE_API_KEY", exc.response.status_code)
            else:
                logger.warning("Massive API error %s, keeping stale cache", exc.response.status_code)
            return
        except httpx.HTTPError as exc:
            logger.warning("Massive API request failed: %s — keeping stale cache", exc)
            return

        now = datetime.now(timezone.utc)
        for entry in data.get("tickers", []):
            self._apply_snapshot(entry, now)

    def _apply_snapshot(self, entry: dict, now: datetime) -> None:
        ticker = entry["ticker"]
        day = entry.get("day") or {}
        prev_day = entry.get("prevDay") or {}
        last_trade = entry.get("lastTrade") or {}

        price = last_trade.get("p") or day.get("c") or prev_day.get("c")
        if price is None:
            return  # no usable price in this snapshot; skip rather than write a bad value

        open_price = day.get("o") or prev_day.get("c") or price
        existing = self._cache.get(ticker)
        previous_price = existing.price if existing else price

        self._cache.set(PriceUpdate(
            ticker=ticker,
            price=round(price, 2),
            previous_price=round(previous_price, 2),
            open_price=round(open_price, 2),
            timestamp=now,
        ))
```

### Error handling

- **Transient network/5xx errors**: log and keep last-known cache values; retry on the next scheduled poll. The background task never dies from a single failed request.
- **Auth failure (401/403)**: logged clearly so it's obvious in server logs that `MASSIVE_API_KEY` is wrong, but the app keeps running (with a frozen/empty cache) rather than crashing — a bad key shouldn't take down the whole terminal.
- **Market closed (weekends/after-hours)**: Massive still returns `prevDay` data; prices in the UI will simply stop changing between sessions. This is expected, not a bug — no special-casing needed for v1.
- **Ticker with no data yet** (e.g., just added, first poll hasn't landed): `_apply_snapshot` requires a price; if Massive omits a ticker from its response entirely (e.g., invalid symbol), the cache simply never gets an entry for it, and the SSE endpoint's `get_many` silently skips it. The watchlist route can validate ticker symbols before insert if stricter behavior is wanted later — out of scope here.

## 7. SSE streaming endpoint

```python
# backend/app/routes/stream.py
import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()
TICK_INTERVAL_SECONDS = 0.5


@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    cache = request.app.state.price_cache
    watchlist = request.app.state.watchlist_tickers  # kept in sync by watchlist routes

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            updates = cache.get_many(watchlist())
            payload = [
                {
                    "ticker": u.ticker,
                    "price": u.price,
                    "previous_price": u.previous_price,
                    "change_direction": u.change_direction,
                    "change_pct": round(u.change_pct, 2),
                    "timestamp": u.timestamp.isoformat(),
                }
                for u in updates
            ]
            yield {"event": "price_update", "data": json.dumps(payload)}
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    return EventSourceResponse(event_generator())
```

**Design decision — one SSE event per tick, batched across all tickers**, rather than one event per ticker. PLAN.md §6 describes the payload per-ticker ("each SSE event contains ticker, price, previous price, timestamp, and change direction"); this design keeps every one of those fields but nests them in a JSON array within a single `price_update` event every 500ms. Rationale: it's one `EventSource.onmessage` parse per tick on the frontend instead of up to ten, and it avoids any question of event ordering/interleaving across tickers within the same tick. Add `sse-starlette` and `httpx` to `backend/pyproject.toml` dependencies.

This handler is intentionally provider-agnostic — it only touches `PriceCache`, never `SimulatorProvider`/`MassiveProvider` directly, so it works unchanged regardless of which provider is active.

## 8. Watchlist changes → provider updates

The watchlist routes (`POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`) are the only place tickers change at runtime. After writing to the `watchlist` table, each route must:

```python
tickers = load_watchlist_tickers(db)          # re-read from DB
app.state.provider.set_tickers(set(tickers))    # push into whichever provider is active
```

`set_tickers` is a full-replacement call (not incremental add/remove) — it's simpler to reason about and cheap enough at this scale (≤ a few dozen tickers) to just recompute the full set on every change rather than tracking deltas.

A freshly-added ticker has no cache entry until the provider's next tick (≤ 500ms for the simulator, ≤ `poll_interval` for Massive — worth surfacing to the frontend that a just-added ticker may show blank/loading for a few seconds before Massive's first snapshot lands, if Massive is active).

## 9. Configuration

| Variable | Effect on this subsystem |
|---|---|
| `MASSIVE_API_KEY` | Empty/absent → `SimulatorProvider`. Non-empty → `MassiveProvider`. Read once at startup (PLAN.md §5). |
| (none for simulator) | `TIME_ACCELERATION`, `SEED_PARAMS` are code constants, not env vars — no product need to tune them at runtime. |

`DEFAULT_POLL_INTERVAL_SECONDS` for Massive is likewise a code constant. If a paid Massive tier is used, raise it in code (lower interval) rather than exposing it as an env var — there's no user-facing reason to make it configurable at runtime.

## 10. Module layout (proposed)

```
backend/app/market_data/
├── __init__.py     # create_market_data_provider() factory
├── base.py         # PriceUpdate, MarketDataProvider ABC
├── cache.py         # PriceCache
├── simulator.py     # SimulatorProvider, gbm_step, SEED_PARAMS
└── massive.py        # MassiveProvider
```

`app.state.price_cache` and `app.state.provider` are created and started in the FastAPI `lifespan` context manager, seeded with the watchlist loaded from the DB at startup, and `provider.stop()` is called on shutdown.

## 11. Testing

Per PLAN.md §12:

- **`gbm_step` math**: given fixed `rng` seed, output is deterministic and reproducible — assert exact values for a known seed, and statistically assert mean/variance over many steps land near theoretical `μ`/`σ` for a large sample.
- **Interface conformance**: a shared pytest suite parametrized over `SimulatorProvider` and `MassiveProvider` (with `httpx` mocked via `respx` or `pytest-httpx`) asserting both: populate the cache after `start()` + one tick/poll, pick up new tickers after `set_tickers()`, and stop cleanly.
- **`MassiveProvider._apply_snapshot`**: unit tests against fixed sample JSON payloads (including the shape above) — correct price/open/previous extraction, and graceful no-op on missing/malformed fields.
- **`PriceCache`**: trivial get/set/get_many/all_tickers behavior, including tickers absent from the cache being silently skipped by `get_many`.
- **SSE endpoint**: integration test hitting `/api/stream/prices`, asserting the event stream yields parseable `price_update` JSON with the expected fields within one tick interval.
