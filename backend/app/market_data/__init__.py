import os

from .base import MarketDataProvider, PriceUpdate
from .cache import PriceCache
from .massive import MassiveProvider
from .simulator import SimulatorProvider

__all__ = [
    "MarketDataProvider",
    "PriceUpdate",
    "PriceCache",
    "MassiveProvider",
    "SimulatorProvider",
    "create_market_data_provider",
]


def create_market_data_provider(cache: PriceCache) -> MarketDataProvider:
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveProvider(cache=cache, api_key=api_key)
    return SimulatorProvider(cache=cache)
