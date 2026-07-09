"""Unified market data provider interface.

Both the simulator and the Massive client implement `MarketDataProvider` and
write into a shared `PriceCache`. Downstream code (SSE streaming, the
frontend) is agnostic to which implementation is active.

See planning/MARKET_DATA_DESIGN.md section 3.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ChangeDirection = Literal["up", "down", "flat"]


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """A single point-in-time price observation for one ticker."""

    ticker: str
    price: float
    previous_price: float
    open_price: float  # session/day reference price, for daily % change
    timestamp: datetime  # UTC

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
