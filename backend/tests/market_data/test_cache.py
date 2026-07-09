from datetime import datetime, timezone

from app.market_data.base import PriceUpdate
from app.market_data.cache import PriceCache

NOW = datetime(2026, 1, 5, 15, 30, tzinfo=timezone.utc)


def _update(ticker: str, price: float) -> PriceUpdate:
    return PriceUpdate(ticker=ticker, price=price, previous_price=price, open_price=price, timestamp=NOW)


def test_get_missing_ticker_returns_none():
    cache = PriceCache()
    assert cache.get("AAPL") is None


def test_set_then_get_returns_latest():
    cache = PriceCache()
    cache.set(_update("AAPL", 190.0))
    assert cache.get("AAPL").price == 190.0


def test_set_overwrites_previous_value():
    cache = PriceCache()
    cache.set(_update("AAPL", 190.0))
    cache.set(_update("AAPL", 191.5))
    assert cache.get("AAPL").price == 191.5


def test_get_many_returns_only_requested_tickers():
    cache = PriceCache()
    cache.set(_update("AAPL", 190.0))
    cache.set(_update("GOOGL", 175.0))
    cache.set(_update("MSFT", 420.0))

    result = cache.get_many({"AAPL", "MSFT"})

    assert {u.ticker for u in result} == {"AAPL", "MSFT"}


def test_get_many_silently_skips_tickers_absent_from_cache():
    cache = PriceCache()
    cache.set(_update("AAPL", 190.0))

    result = cache.get_many({"AAPL", "NFLX"})

    assert [u.ticker for u in result] == ["AAPL"]


def test_get_many_empty_request_returns_empty_list():
    cache = PriceCache()
    cache.set(_update("AAPL", 190.0))
    assert cache.get_many(set()) == []


def test_all_tickers_reflects_every_ticker_ever_set():
    cache = PriceCache()
    cache.set(_update("AAPL", 190.0))
    cache.set(_update("GOOGL", 175.0))
    assert cache.all_tickers() == {"AAPL", "GOOGL"}


def test_removing_from_watchlist_does_not_delete_cache_entry():
    # Removing a ticker from the watchlist doesn't clear the cache — the row
    # simply stops being requested via get_many once the tracked set shrinks.
    cache = PriceCache()
    cache.set(_update("AAPL", 190.0))
    watchlist = {"GOOGL"}  # AAPL was just removed from the watchlist
    assert cache.get_many(watchlist) == []
    assert cache.get("AAPL") is not None
