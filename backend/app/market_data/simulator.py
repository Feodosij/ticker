"""GBM-based market data simulator (default provider when MASSIVE_API_KEY is unset).

See planning/MARKET_DATA_DESIGN.md section 5.
"""

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
# tick without looking absurd. Tune freely — see MARKET_DATA_DESIGN.md §5.
TIME_ACCELERATION = 50
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # ~5,896,800


@dataclass
class TickerParams:
    seed_price: float
    mu: float  # annualized drift, e.g. 0.10 = 10%/yr
    sigma: float  # annualized volatility, e.g. 0.30 = 30%/yr


# Default watchlist (PLAN.md §7). Prices/params are illustrative, not live
# quotes — chosen to give each name a distinct personality on screen.
SEED_PARAMS: dict[str, TickerParams] = {
    "AAPL": TickerParams(190.00, mu=0.10, sigma=0.28),
    "GOOGL": TickerParams(175.00, mu=0.09, sigma=0.30),
    "MSFT": TickerParams(420.00, mu=0.10, sigma=0.26),
    "AMZN": TickerParams(185.00, mu=0.11, sigma=0.32),
    "TSLA": TickerParams(250.00, mu=0.05, sigma=0.55),
    "NVDA": TickerParams(130.00, mu=0.15, sigma=0.50),
    "META": TickerParams(500.00, mu=0.10, sigma=0.34),
    "JPM": TickerParams(210.00, mu=0.07, sigma=0.22),
    "V": TickerParams(275.00, mu=0.08, sigma=0.20),
    "NFLX": TickerParams(680.00, mu=0.09, sigma=0.35),
}

# Fallback for tickers added at runtime that aren't in SEED_PARAMS (the
# simulator has no real quote to seed from). Mid-range price, market-ish vol.
DEFAULT_PARAMS = TickerParams(seed_price=100.00, mu=0.08, sigma=0.30)


def gbm_step(price: float, mu: float, sigma: float, dt_years: float, rng: random.Random) -> float:
    """One geometric Brownian motion step: S(t+dt) = S(t) * exp[(mu - sigma^2/2)*dt + sigma*sqrt(dt)*Z]."""
    z = rng.gauss(0.0, 1.0)
    drift = (mu - 0.5 * sigma**2) * dt_years
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
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def tick(self) -> None:
        """Advance every tracked ticker by one GBM step and write it to the cache.

        Exposed as a synchronous method (separate from the sleep loop) so
        tests can drive individual ticks deterministically without waiting
        on real time.
        """
        now = datetime.now(timezone.utc)
        for ticker, state in self._state.items():
            new_price = gbm_step(state.price, state.params.mu, state.params.sigma, self._dt_years, self._rng)
            new_price = round(new_price, 2)
            self._cache.set(
                PriceUpdate(
                    ticker=ticker,
                    price=new_price,
                    previous_price=state.price,
                    open_price=state.open_price,
                    timestamp=now,
                )
            )
            state.price = new_price

    async def _run(self) -> None:
        while True:
            self.tick()
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
