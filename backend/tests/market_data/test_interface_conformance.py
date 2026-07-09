"""Shared behavioral contract that every MarketDataProvider implementation must satisfy.

Parametrized over SimulatorProvider and MassiveProvider (with httpx mocked)
per planning/MARKET_DATA_DESIGN.md section 11.
"""

import asyncio

import httpx
import pytest

from app.market_data.base import MarketDataProvider
from app.market_data.cache import PriceCache
from app.market_data.massive import MassiveProvider
from app.market_data.simulator import SimulatorProvider


def _massive_snapshot_handler(request: httpx.Request) -> httpx.Response:
    query = request.url.params
    tickers = query.get("tickers", "").split(",") if query.get("tickers") else []
    return httpx.Response(
        200,
        json={"status": "OK", "tickers": [{"ticker": t, "lastTrade": {"p": 100.0}} for t in tickers]},
    )


def make_simulator(cache: PriceCache) -> MarketDataProvider:
    return SimulatorProvider(cache=cache, seed=1)


def make_massive(cache: PriceCache) -> MarketDataProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(_massive_snapshot_handler), base_url="https://api.massive.com")
    return MassiveProvider(cache=cache, api_key="test-key", poll_interval=0.05, client=client)


PROVIDER_FACTORIES = [make_simulator, make_massive]
PROVIDER_IDS = ["simulator", "massive"]


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES, ids=PROVIDER_IDS)
async def test_provider_populates_cache_after_start_and_one_tick(factory):
    cache = PriceCache()
    provider = factory(cache)
    provider.set_tickers({"AAPL"})

    await provider.start()
    try:
        for _ in range(50):
            if cache.get("AAPL") is not None:
                break
            await asyncio.sleep(0.05)
    finally:
        await provider.stop()

    assert cache.get("AAPL") is not None


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES, ids=PROVIDER_IDS)
async def test_provider_picks_up_new_tickers_after_set_tickers_without_restart(factory):
    cache = PriceCache()
    provider = factory(cache)
    provider.set_tickers({"AAPL"})

    await provider.start()
    try:
        for _ in range(50):
            if cache.get("AAPL") is not None:
                break
            await asyncio.sleep(0.05)

        provider.set_tickers({"AAPL", "NVDA"})

        for _ in range(50):
            if cache.get("NVDA") is not None:
                break
            await asyncio.sleep(0.05)
    finally:
        await provider.stop()

    assert cache.get("NVDA") is not None


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES, ids=PROVIDER_IDS)
async def test_provider_stops_cleanly_and_can_be_started_again(factory):
    cache = PriceCache()
    provider = factory(cache)
    provider.set_tickers({"AAPL"})

    await provider.start()
    await provider.stop()

    # A second start/stop cycle must not raise or hang.
    await provider.start()
    await provider.stop()


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES, ids=PROVIDER_IDS)
def test_provider_implements_the_market_data_provider_interface(factory):
    provider = factory(PriceCache())
    assert isinstance(provider, MarketDataProvider)
