import asyncio
import json

from app.routes.stream import stream_prices

from .conftest import set_price


def trade(client, ticker, quantity, side):
    return client.post(
        "/api/portfolio/trade",
        json={"ticker": ticker, "quantity": quantity, "side": side},
    )


# --- health ----------------------------------------------------------------


async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- watchlist -------------------------------------------------------------


async def test_get_watchlist_default_seed(client):
    resp = await client.get("/api/watchlist")
    assert resp.status_code == 200
    tickers = {e["ticker"] for e in resp.json()}
    assert tickers == {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                       "NVDA", "META", "JPM", "V", "NFLX"}


async def test_watchlist_entry_null_price_when_no_cache(client):
    entries = (await client.get("/api/watchlist")).json()
    entry = next(e for e in entries if e["ticker"] == "AAPL")
    assert entry["price"] is None
    assert entry["previous_price"] is None
    assert entry["change_direction"] is None
    assert entry["change_pct"] is None
    assert entry["added_at"]


async def test_watchlist_entry_merges_price(client):
    set_price(client, "AAPL", 195.2, previous_price=194.8, open_price=192.9)
    entries = (await client.get("/api/watchlist")).json()
    entry = next(e for e in entries if e["ticker"] == "AAPL")
    assert entry["price"] == 195.2
    assert entry["previous_price"] == 194.8
    assert entry["change_direction"] == "up"
    assert entry["change_pct"] == round((195.2 - 192.9) / 192.9 * 100, 2)


async def test_add_watchlist(client):
    resp = await client.post("/api/watchlist", json={"ticker": "pypl"})
    assert resp.status_code == 201
    assert resp.json()["ticker"] == "PYPL"
    entries = (await client.get("/api/watchlist")).json()
    assert "PYPL" in {e["ticker"] for e in entries}


async def test_add_watchlist_syncs_provider(client):
    await client.post("/api/watchlist", json={"ticker": "PYPL"})
    last_call = client.app.state.provider.ticker_calls[-1]
    assert "PYPL" in last_call


async def test_add_watchlist_idempotent_returns_200(client):
    resp = await client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "AAPL"


async def test_delete_watchlist(client):
    resp = await client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 204
    entries = (await client.get("/api/watchlist")).json()
    assert "AAPL" not in {e["ticker"] for e in entries}
    assert "AAPL" not in client.app.state.provider.ticker_calls[-1]


async def test_delete_watchlist_missing_404(client):
    resp = await client.delete("/api/watchlist/ZZZZ")
    assert resp.status_code == 404
    assert "detail" in resp.json()


# --- portfolio -------------------------------------------------------------


async def test_get_portfolio_empty(client):
    resp = await client.get("/api/portfolio")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cash_balance"] == 10000.0
    assert body["positions"] == []
    assert body["total_value"] == 10000.0
    assert body["total_unrealized_pnl"] == 0.0


async def test_get_portfolio_with_position(client):
    set_price(client, "AAPL", 195.0)
    await trade(client, "AAPL", 10, "buy")
    body = (await client.get("/api/portfolio")).json()
    pos = body["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 195.0
    assert pos["current_price"] == 195.0
    assert pos["unrealized_pnl"] == 0.0
    assert body["cash_balance"] == 8050.0
    assert body["total_value"] == 10000.0


# --- trades ----------------------------------------------------------------


async def test_buy_happy_path(client):
    set_price(client, "AAPL", 190.0)
    resp = await trade(client, "AAPL", 10, "buy")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trade"]["side"] == "buy"
    assert body["trade"]["price"] == 190.0
    assert body["cash_balance"] == 10000.0 - 1900.0
    assert body["position"]["quantity"] == 10
    assert body["position"]["avg_cost"] == 190.0


async def test_buy_weighted_average_cost(client):
    set_price(client, "AAPL", 100.0)
    await trade(client, "AAPL", 10, "buy")
    set_price(client, "AAPL", 200.0)
    resp = await trade(client, "AAPL", 10, "buy")
    pos = resp.json()["position"]
    assert pos["quantity"] == 20
    assert pos["avg_cost"] == 150.0


async def test_buy_insufficient_cash(client):
    set_price(client, "AAPL", 190.0)
    resp = await trade(client, "AAPL", 1000, "buy")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "insufficient cash"


async def test_partial_sell(client):
    set_price(client, "AAPL", 100.0)
    await trade(client, "AAPL", 10, "buy")
    set_price(client, "AAPL", 120.0)
    resp = await trade(client, "AAPL", 4, "sell")
    assert resp.status_code == 200
    body = resp.json()
    assert body["position"]["quantity"] == 6
    assert body["position"]["avg_cost"] == 100.0
    assert body["cash_balance"] == 9480.0


async def test_full_sell_removes_position(client):
    set_price(client, "AAPL", 100.0)
    await trade(client, "AAPL", 10, "buy")
    resp = await trade(client, "AAPL", 10, "sell")
    assert resp.status_code == 200
    assert resp.json()["position"] is None
    body = (await client.get("/api/portfolio")).json()
    assert body["positions"] == []


async def test_sell_insufficient_shares(client):
    set_price(client, "AAPL", 100.0)
    await trade(client, "AAPL", 5, "buy")
    resp = await trade(client, "AAPL", 10, "sell")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "insufficient shares"


async def test_sell_with_no_position(client):
    set_price(client, "AAPL", 100.0)
    resp = await trade(client, "AAPL", 1, "sell")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "insufficient shares"


async def test_trade_no_price_available(client):
    resp = await trade(client, "AAPL", 10, "buy")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "no price available for AAPL"


async def test_trade_non_positive_quantity(client):
    set_price(client, "AAPL", 100.0)
    resp = await trade(client, "AAPL", 0, "buy")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "quantity must be greater than 0"


# --- portfolio history -----------------------------------------------------


async def test_portfolio_history_records_on_trade(client):
    set_price(client, "AAPL", 100.0)
    await trade(client, "AAPL", 10, "buy")
    resp = await client.get("/api/portfolio/history")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) >= 1
    assert "total_value" in history[0]
    assert "recorded_at" in history[0]


# --- SSE -------------------------------------------------------------------


class _FakeRequest:
    """Minimal stand-in for the SSE handler. httpx's ASGITransport buffers the
    whole response body, so it can never consume an endless SSE stream; instead
    we drive the handler's generator directly. Provides just what the handler
    touches: app.state and a non-disconnecting is_disconnected()."""

    def __init__(self, app):
        self.app = app

    async def is_disconnected(self):
        return False


async def test_stream_prices_yields_price_update(client):
    set_price(client, "AAPL", 195.2, previous_price=194.8, open_price=192.9)

    response = await stream_prices(_FakeRequest(client.app))
    generator = response.body_iterator
    try:
        event = await asyncio.wait_for(generator.__anext__(), timeout=5)
    finally:
        await generator.aclose()

    assert event["event"] == "price_update"
    payload = json.loads(event["data"])
    aapl = next(p for p in payload if p["ticker"] == "AAPL")
    assert aapl["price"] == 195.2
    assert aapl["previous_price"] == 194.8
    assert aapl["change_direction"] == "up"
    assert "timestamp" in aapl
