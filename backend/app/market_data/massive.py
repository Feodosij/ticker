"""Massive (Polygon.io) REST API provider.

Polls the full-market snapshot endpoint for the watchlist on a fixed
interval. Never exceeds the API rate limit regardless of watchlist size
(one request per poll covers every tracked ticker), and degrades gracefully
(stale cache, not a crash) on network or auth failures.

See planning/MARKET_DATA_DESIGN.md section 6.
"""

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
    def __init__(
        self,
        cache: PriceCache,
        api_key: str,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._cache = cache
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)

    def set_tickers(self, tickers: set[str]) -> None:
        self._tickers = set(tickers)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._owns_client:
            await self._client.aclose()

    async def _run(self) -> None:
        while True:
            if self._tickers:
                await self.poll_once()
            await asyncio.sleep(self._poll_interval)

    async def poll_once(self) -> None:
        """Fetch and apply one snapshot for the currently tracked tickers.

        Public (not `_poll_once`) so tests can drive a single poll cycle
        deterministically without waiting on the background loop.
        """
        params = {"tickers": ",".join(sorted(self._tickers)), "apiKey": self._api_key}
        try:
            resp = await self._client.get(SNAPSHOT_PATH, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                logger.error(
                    "Massive API rejected the API key (HTTP %s) — check MASSIVE_API_KEY",
                    exc.response.status_code,
                )
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
        ticker = entry.get("ticker")
        if not ticker:
            return

        day = entry.get("day") or {}
        prev_day = entry.get("prevDay") or {}
        last_trade = entry.get("lastTrade") or {}

        price = last_trade.get("p") or day.get("c") or prev_day.get("c")
        if price is None:
            return  # no usable price in this snapshot; skip rather than write a bad value

        open_price = day.get("o") or prev_day.get("c") or price
        existing = self._cache.get(ticker)
        previous_price = existing.price if existing else price

        self._cache.set(
            PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                open_price=round(open_price, 2),
                timestamp=now,
            )
        )
