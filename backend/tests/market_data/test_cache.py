from datetime import UTC, datetime

from app.market_data.base import PriceUpdate
from app.market_data.cache import PriceCache


def make_update(ticker, price=100.0):
    return PriceUpdate(
        ticker=ticker,
        price=price,
        previous_price=price,
        open_price=price,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
    )


def test_get_missing_ticker_returns_none():
    cache = PriceCache()
    assert cache.get("AAPL") is None


def test_set_price_then_get():
    cache = PriceCache()
    update = make_update("AAPL")
    cache.set_price(update)
    assert cache.get("AAPL") is update


def test_set_price_overwrites_previous_value():
    cache = PriceCache()
    cache.set_price(make_update("AAPL", price=100.0))
    second = make_update("AAPL", price=101.0)
    cache.set_price(second)
    assert cache.get("AAPL") is second


def test_get_many_returns_only_known_tickers():
    cache = PriceCache()
    cache.set_price(make_update("AAPL"))
    cache.set_price(make_update("MSFT"))
    result = cache.get_many({"AAPL", "MSFT", "GOOGL"})
    tickers = {u.ticker for u in result}
    assert tickers == {"AAPL", "MSFT"}


def test_get_many_empty_set_returns_empty_list():
    cache = PriceCache()
    cache.set_price(make_update("AAPL"))
    assert cache.get_many(set()) == []


def test_all_tickers():
    cache = PriceCache()
    cache.set_price(make_update("AAPL"))
    cache.set_price(make_update("MSFT"))
    assert cache.all_tickers() == {"AAPL", "MSFT"}


def test_all_tickers_empty_cache():
    cache = PriceCache()
    assert cache.all_tickers() == set()
