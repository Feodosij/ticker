import asyncio

import httpx
import pytest

from app.market_data.cache import PriceCache
from app.market_data.massive import BASE_URL, MassiveProvider
from app.market_data.simulator import SimulatorProvider


def _massive_snapshot_handler(request: httpx.Request) -> httpx.Response:
    raw_tickers = request.url.params.get("tickers") or ""
    payload = [
        {"ticker": t, "lastTrade": {"p": 100.0}, "day": {"o": 100.0}}
        for t in raw_tickers.split(",")
        if t
    ]
    return httpx.Response(200, json={"status": "OK", "tickers": payload})


def make_simulator(cache: PriceCache) -> SimulatorProvider:
    return SimulatorProvider(cache=cache, seed=7, tick_interval_seconds=0.01)


def make_massive(cache: PriceCache) -> MassiveProvider:
    client = httpx.AsyncClient(
        base_url=BASE_URL,
        transport=httpx.MockTransport(_massive_snapshot_handler),
    )
    return MassiveProvider(cache=cache, api_key="test-key", poll_interval=0.01, client=client)


PROVIDER_FACTORIES = [make_simulator, make_massive]
PROVIDER_IDS = ["simulator", "massive"]


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES, ids=PROVIDER_IDS)
async def test_provider_populates_cache_after_start_and_one_tick(factory):
    cache = PriceCache()
    provider = factory(cache)
    provider.set_tickers({"AAPL"})
    await provider.start()
    try:
        await asyncio.sleep(0.05)
        assert cache.get("AAPL") is not None
    finally:
        await provider.stop()


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES, ids=PROVIDER_IDS)
async def test_provider_picks_up_new_tickers_after_set_tickers(factory):
    cache = PriceCache()
    provider = factory(cache)
    provider.set_tickers({"AAPL"})
    await provider.start()
    try:
        await asyncio.sleep(0.05)
        provider.set_tickers({"AAPL", "MSFT"})
        await asyncio.sleep(0.05)
        assert cache.get("MSFT") is not None
    finally:
        await provider.stop()


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES, ids=PROVIDER_IDS)
async def test_provider_stops_cleanly(factory):
    cache = PriceCache()
    provider = factory(cache)
    provider.set_tickers({"AAPL"})
    await provider.start()
    await provider.stop()
    assert provider._task is None
