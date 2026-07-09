"""Market data subsystem: unified provider interface, simulator, and Massive client.

See planning/MARKET_DATA_DESIGN.md for the full design.
"""

import os

from .base import MarketDataProvider, PriceUpdate
from .cache import PriceCache
from .massive import MassiveProvider
from .simulator import SimulatorProvider

__all__ = [
    "MarketDataProvider",
    "PriceUpdate",
    "PriceCache",
    "SimulatorProvider",
    "MassiveProvider",
    "create_market_data_provider",
]


def create_market_data_provider(cache: PriceCache) -> MarketDataProvider:
    """Select the active provider based on MASSIVE_API_KEY (read once at startup).

    Empty/absent -> SimulatorProvider. Non-empty -> MassiveProvider.
    """
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveProvider(cache=cache, api_key=api_key)
    return SimulatorProvider(cache=cache)
