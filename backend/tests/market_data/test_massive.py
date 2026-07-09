import asyncio
from datetime import datetime, timezone

import httpx

from app.market_data.cache import PriceCache
from app.market_data.massive import SNAPSHOT_PATH, MassiveProvider

NOW = datetime(2026, 1, 5, 15, 30, tzinfo=timezone.utc)


def _client_for(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="https://api.massive.com")


def _json_handler(payload: dict, status_code: int = 200, calls: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return httpx.Response(status_code, json=payload)

    return handler


# --- _apply_snapshot -------------------------------------------------------


def test_apply_snapshot_extracts_price_open_and_previous_from_last_trade():
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(_json_handler({})))

    provider._apply_snapshot(
        {
            "ticker": "AAPL",
            "lastTrade": {"p": 190.42},
            "day": {"o": 189.10, "c": 190.42},
            "prevDay": {"o": 187.00, "c": 189.00},
        },
        NOW,
    )

    update = cache.get("AAPL")
    assert update.price == 190.42
    assert update.open_price == 189.10
    # No prior cache entry, so previous_price falls back to the current price.
    assert update.previous_price == 190.42


def test_apply_snapshot_falls_back_to_day_close_when_no_last_trade():
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(_json_handler({})))

    provider._apply_snapshot({"ticker": "AAPL", "day": {"o": 189.10, "c": 190.00}, "prevDay": {}}, NOW)

    assert cache.get("AAPL").price == 190.00


def test_apply_snapshot_falls_back_to_prev_day_close_when_no_day_data():
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(_json_handler({})))

    provider._apply_snapshot({"ticker": "AAPL", "prevDay": {"c": 189.00}}, NOW)

    assert cache.get("AAPL").price == 189.00


def test_apply_snapshot_falls_back_open_price_to_prev_day_close():
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(_json_handler({})))

    provider._apply_snapshot(
        {"ticker": "AAPL", "lastTrade": {"p": 190.0}, "day": {}, "prevDay": {"c": 188.5}},
        NOW,
    )

    assert cache.get("AAPL").open_price == 188.5


def test_apply_snapshot_open_price_falls_back_to_price_when_nothing_else_available():
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(_json_handler({})))

    provider._apply_snapshot({"ticker": "AAPL", "lastTrade": {"p": 190.0}}, NOW)

    assert cache.get("AAPL").open_price == 190.0


def test_apply_snapshot_uses_existing_cache_price_as_previous_price():
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(_json_handler({})))

    provider._apply_snapshot({"ticker": "AAPL", "lastTrade": {"p": 190.0}}, NOW)
    provider._apply_snapshot({"ticker": "AAPL", "lastTrade": {"p": 192.0}}, NOW)

    update = cache.get("AAPL")
    assert update.price == 192.0
    assert update.previous_price == 190.0


def test_apply_snapshot_with_no_usable_price_is_skipped():
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(_json_handler({})))

    provider._apply_snapshot({"ticker": "GHOST", "day": {}, "prevDay": {}}, NOW)

    assert cache.get("GHOST") is None


def test_apply_snapshot_with_missing_ticker_field_is_skipped_gracefully():
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(_json_handler({})))

    # Should not raise even though "ticker" is absent.
    provider._apply_snapshot({"lastTrade": {"p": 190.0}}, NOW)

    assert cache.all_tickers() == set()


def test_apply_snapshot_with_malformed_nested_fields_does_not_raise():
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(_json_handler({})))

    provider._apply_snapshot({"ticker": "AAPL", "day": None, "prevDay": None, "lastTrade": None}, NOW)

    assert cache.get("AAPL") is None


# --- poll_once (HTTP layer) -------------------------------------------------


async def test_poll_once_populates_cache_for_every_ticker_in_the_response():
    payload = {
        "status": "OK",
        "tickers": [
            {"ticker": "AAPL", "lastTrade": {"p": 190.42}, "day": {"o": 189.10}},
            {"ticker": "GOOGL", "lastTrade": {"p": 175.20}, "day": {"o": 174.00}},
        ],
    }
    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="secret", client=_client_for(_json_handler(payload)))
    provider.set_tickers({"AAPL", "GOOGL"})

    await provider.poll_once()

    assert cache.get("AAPL").price == 190.42
    assert cache.get("GOOGL").price == 175.20


async def test_poll_once_sends_comma_separated_tickers_and_api_key():
    calls: list[httpx.Request] = []
    payload = {"status": "OK", "tickers": []}
    provider = MassiveProvider(
        cache=PriceCache(), api_key="secret-key", client=_client_for(_json_handler(payload, calls=calls))
    )
    provider.set_tickers({"AAPL", "MSFT", "GOOGL"})

    await provider.poll_once()

    assert len(calls) == 1
    request = calls[0]
    assert request.url.path == SNAPSHOT_PATH
    query = request.url.params
    assert query["tickers"] == "AAPL,GOOGL,MSFT"  # sorted, deterministic order
    assert query["apiKey"] == "secret-key"


async def test_poll_once_on_auth_failure_keeps_cache_stale_without_raising():
    cache = PriceCache()
    provider = MassiveProvider(
        cache=cache, api_key="bad-key", client=_client_for(_json_handler({"error": "unauthorized"}, status_code=401))
    )
    provider.set_tickers({"AAPL"})

    await provider.poll_once()  # must not raise

    assert cache.get("AAPL") is None


async def test_poll_once_on_server_error_keeps_cache_stale_without_raising():
    cache = PriceCache()
    provider = MassiveProvider(
        cache=cache, api_key="k", client=_client_for(_json_handler({}, status_code=503))
    )
    provider.set_tickers({"AAPL"})

    await provider.poll_once()  # must not raise

    assert cache.get("AAPL") is None


async def test_poll_once_on_network_error_keeps_cache_stale_without_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    cache = PriceCache()
    provider = MassiveProvider(cache=cache, api_key="k", client=_client_for(handler))
    provider.set_tickers({"AAPL"})

    await provider.poll_once()  # must not raise

    assert cache.get("AAPL") is None


async def test_poll_once_on_transient_error_does_not_clobber_previously_cached_price():
    cache = PriceCache()
    good_client = _client_for(_json_handler({"tickers": [{"ticker": "AAPL", "lastTrade": {"p": 190.0}}]}))
    provider = MassiveProvider(cache=cache, api_key="k", client=good_client)
    provider.set_tickers({"AAPL"})
    await provider.poll_once()
    assert cache.get("AAPL").price == 190.0

    # Swap in a failing client to simulate the next poll erroring.
    provider._client = _client_for(_json_handler({}, status_code=500))
    await provider.poll_once()

    assert cache.get("AAPL").price == 190.0  # stale value preserved, not wiped


# --- background loop ---------------------------------------------------


async def test_run_skips_polling_when_no_tickers_are_tracked():
    calls: list[httpx.Request] = []
    provider = MassiveProvider(
        cache=PriceCache(),
        api_key="k",
        poll_interval=0.05,
        client=_client_for(_json_handler({"tickers": []}, calls=calls)),
    )

    await provider.start()
    try:
        await asyncio.sleep(0.2)
    finally:
        await provider.stop()

    assert calls == []


async def test_start_and_stop_runs_poll_loop_and_cancels_cleanly():
    cache = PriceCache()
    payload = {"tickers": [{"ticker": "AAPL", "lastTrade": {"p": 190.0}}]}
    provider = MassiveProvider(
        cache=cache, api_key="k", poll_interval=0.05, client=_client_for(_json_handler(payload))
    )
    provider.set_tickers({"AAPL"})

    await provider.start()
    try:
        for _ in range(50):
            if cache.get("AAPL") is not None:
                break
            await asyncio.sleep(0.02)
    finally:
        await provider.stop()

    assert cache.get("AAPL") is not None
    assert provider._task is None
