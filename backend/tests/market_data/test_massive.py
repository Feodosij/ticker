import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from app.market_data.base import PriceUpdate
from app.market_data.cache import PriceCache
from app.market_data.massive import BASE_URL, SNAPSHOT_PATH, MassiveProvider


def make_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url=BASE_URL, transport=transport)


def snapshot_handler(tickers_payload, status_code=200):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == SNAPSHOT_PATH
        return httpx.Response(status_code, json={"status": "OK", "tickers": tickers_payload})

    return handler


def unreachable_handler(request: httpx.Request) -> httpx.Response:
    raise AssertionError("HTTP client should not be called in this test")


def make_provider(cache, api_key="test-key", poll_interval=15.0, handler=unreachable_handler):
    return MassiveProvider(
        cache=cache,
        api_key=api_key,
        poll_interval=poll_interval,
        client=make_client(handler),
    )


# --- _apply_snapshot -----------------------------------------------------


def test_apply_snapshot_prefers_last_trade_price():
    cache = PriceCache()
    provider = make_provider(cache)
    provider._apply_snapshot(
        {
            "ticker": "AAPL",
            "lastTrade": {"p": 190.42},
            "day": {"o": 189.10, "c": 190.00},
            "prevDay": {"c": 189.00},
        },
        datetime.now(UTC),
    )
    update = cache.get("AAPL")
    assert update.price == pytest.approx(190.42)
    assert update.open_price == pytest.approx(189.10)


def test_apply_snapshot_falls_back_to_day_close_when_no_last_trade():
    cache = PriceCache()
    provider = make_provider(cache)
    provider._apply_snapshot(
        {"ticker": "AAPL", "day": {"o": 100.0, "c": 105.0}},
        datetime.now(UTC),
    )
    update = cache.get("AAPL")
    assert update.price == pytest.approx(105.0)
    assert update.open_price == pytest.approx(100.0)


def test_apply_snapshot_falls_back_to_prev_day_close_when_no_current_data():
    cache = PriceCache()
    provider = make_provider(cache)
    provider._apply_snapshot(
        {"ticker": "AAPL", "prevDay": {"c": 95.0}},
        datetime.now(UTC),
    )
    update = cache.get("AAPL")
    assert update.price == pytest.approx(95.0)
    assert update.open_price == pytest.approx(95.0)


def test_apply_snapshot_open_price_falls_back_to_prev_close_when_day_open_missing():
    cache = PriceCache()
    provider = make_provider(cache)
    provider._apply_snapshot(
        {"ticker": "AAPL", "lastTrade": {"p": 101.0}, "prevDay": {"c": 99.0}},
        datetime.now(UTC),
    )
    update = cache.get("AAPL")
    assert update.open_price == pytest.approx(99.0)


def test_apply_snapshot_missing_price_fields_is_a_noop():
    cache = PriceCache()
    provider = make_provider(cache)
    provider._apply_snapshot({"ticker": "AAPL"}, datetime.now(UTC))
    assert cache.get("AAPL") is None


def test_apply_snapshot_uses_prior_cached_price_as_previous_price():
    cache = PriceCache()
    cache.set_price(
        PriceUpdate(
            ticker="AAPL",
            price=190.00,
            previous_price=189.00,
            open_price=189.00,
            timestamp=datetime.now(UTC),
        )
    )
    provider = make_provider(cache)
    provider._apply_snapshot(
        {"ticker": "AAPL", "lastTrade": {"p": 191.00}, "day": {"o": 189.00}},
        datetime.now(UTC),
    )
    update = cache.get("AAPL")
    assert update.price == pytest.approx(191.00)
    assert update.previous_price == pytest.approx(190.00)


def test_apply_snapshot_first_sighting_uses_price_as_previous_price():
    cache = PriceCache()
    provider = make_provider(cache)
    provider._apply_snapshot(
        {"ticker": "AAPL", "lastTrade": {"p": 190.42}, "day": {"o": 189.10}},
        datetime.now(UTC),
    )
    update = cache.get("AAPL")
    assert update.previous_price == pytest.approx(190.42)


# --- _poll_once ------------------------------------------------------------


async def test_poll_once_updates_cache_from_snapshot():
    cache = PriceCache()
    payload = [
        {
            "ticker": "AAPL",
            "lastTrade": {"p": 190.42},
            "day": {"o": 189.10, "c": 190.42},
            "prevDay": {"o": 187.00, "c": 189.00},
        }
    ]
    provider = make_provider(cache, handler=snapshot_handler(payload))
    provider.set_tickers({"AAPL"})
    await provider._poll_once()
    update = cache.get("AAPL")
    assert update is not None
    assert update.price == pytest.approx(190.42)
    await provider._client.aclose()


async def test_poll_once_auth_failure_keeps_stale_cache():
    cache = PriceCache()
    stale = PriceUpdate(
        ticker="AAPL",
        price=100.0,
        previous_price=100.0,
        open_price=100.0,
        timestamp=datetime.now(UTC),
    )
    cache.set_price(stale)
    provider = make_provider(cache, handler=snapshot_handler([], status_code=401))
    provider.set_tickers({"AAPL"})
    await provider._poll_once()
    assert cache.get("AAPL") is stale
    await provider._client.aclose()


async def test_poll_once_server_error_keeps_stale_cache():
    cache = PriceCache()
    provider = make_provider(cache, handler=snapshot_handler([], status_code=500))
    provider.set_tickers({"AAPL"})
    await provider._poll_once()
    assert cache.get("AAPL") is None
    await provider._client.aclose()


async def test_poll_once_network_error_does_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    cache = PriceCache()
    provider = make_provider(cache, handler=handler)
    provider.set_tickers({"AAPL"})
    await provider._poll_once()
    assert cache.get("AAPL") is None
    await provider._client.aclose()


async def test_poll_once_sends_sorted_comma_separated_tickers_and_api_key():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["tickers"] = request.url.params.get("tickers")
        captured["apiKey"] = request.url.params.get("apiKey")
        return httpx.Response(200, json={"status": "OK", "tickers": []})

    cache = PriceCache()
    provider = make_provider(cache, api_key="secret-key", handler=handler)
    provider.set_tickers({"MSFT", "AAPL"})
    await provider._poll_once()
    assert captured["tickers"] == "AAPL,MSFT"
    assert captured["apiKey"] == "secret-key"
    await provider._client.aclose()


# --- _run loop ---------------------------------------------------------


async def test_run_skips_poll_when_no_tickers_tracked():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"status": "OK", "tickers": []})

    cache = PriceCache()
    provider = make_provider(cache, poll_interval=0.01, handler=handler)
    await provider.start()
    await asyncio.sleep(0.03)
    await provider.stop()
    assert calls["count"] == 0


async def test_run_polls_periodically_for_tracked_tickers():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"status": "OK", "tickers": []})

    cache = PriceCache()
    provider = make_provider(cache, poll_interval=0.01, handler=handler)
    provider.set_tickers({"AAPL"})
    await provider.start()
    await asyncio.sleep(0.05)
    await provider.stop()
    assert calls["count"] >= 2


async def test_stop_closes_the_http_client():
    cache = PriceCache()
    provider = make_provider(cache, poll_interval=0.01, handler=snapshot_handler([]))
    await provider.start()
    await provider.stop()
    assert provider._client.is_closed
