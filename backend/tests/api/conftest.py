from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import db
from app.market_data.base import PriceUpdate


class FakeProvider:
    """No-op provider so the real simulator's background task doesn't overwrite
    prices we inject into the cache during tests. Records set_tickers calls so
    watchlist routes can be asserted against."""

    def __init__(self) -> None:
        self.ticker_calls: list[set[str]] = []

    def set_tickers(self, tickers: set[str]) -> None:
        self.ticker_calls.append(set(tickers))

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    db.reset_connection()

    import app.main as main

    monkeypatch.setattr(main, "create_market_data_provider", lambda cache: FakeProvider())

    async with main.app.router.lifespan_context(main.app):
        transport = ASGITransport(app=main.app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            c.app = main.app
            yield c

    db.reset_connection()


def set_price(client, ticker, price, previous_price=None, open_price=None):
    prev = previous_price if previous_price is not None else price
    opn = open_price if open_price is not None else price
    client.app.state.price_cache.set_price(
        PriceUpdate(
            ticker=ticker,
            price=price,
            previous_price=prev,
            open_price=opn,
            timestamp=datetime.now(UTC),
        )
    )
