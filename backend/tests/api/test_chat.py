import json

import pytest

from app import db
from app.llm import ChatLLMResponse, ChatTrade, ChatWatchlistChange

from .conftest import set_price


def _fake_completion(response_model: ChatLLMResponse):
    """Return a monkeypatch target for litellm.completion that yields a fixed
    structured response, mimicking OpenRouter's JSON content."""

    class _Msg:
        content = response_model.model_dump_json()

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    def _completion(*args, **kwargs):
        return _Resp()

    return _completion


@pytest.mark.asyncio
async def test_structured_parsing_and_message(client, monkeypatch):
    import app.llm as llm

    monkeypatch.setattr(
        llm.litellm,
        "completion",
        _fake_completion(ChatLLMResponse(message="Hello from Ticker")),
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    resp = await client.post("/api/chat", json={"message": "hi"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Hello from Ticker"
    assert data["trades"] == []
    assert data["watchlist_changes"] == []

    messages = db.list_chat_messages()
    assert messages[-2]["role"] == "user"
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["actions"] == {"trades": [], "watchlist_changes": []}


@pytest.mark.asyncio
async def test_trade_auto_execution_success(client, monkeypatch):
    import app.llm as llm

    set_price(client, "AAPL", 100.0)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        llm.litellm,
        "completion",
        _fake_completion(
            ChatLLMResponse(
                message="Buying AAPL",
                trades=[ChatTrade(ticker="AAPL", side="buy", quantity=2)],
            )
        ),
    )

    resp = await client.post("/api/chat", json={"message": "buy stuff"})
    data = resp.json()
    assert len(data["trades"]) == 1
    trade = data["trades"][0]
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 2
    assert trade["price"] == 100.0
    assert "executed_at" in trade
    assert "error" not in trade

    profile = db.get_profile()
    assert profile["cash_balance"] == pytest.approx(10000.0 - 200.0)


@pytest.mark.asyncio
async def test_trade_failure_does_not_abort_others(client, monkeypatch):
    import app.llm as llm

    set_price(client, "AAPL", 100.0)
    set_price(client, "MSFT", 50.0)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        llm.litellm,
        "completion",
        _fake_completion(
            ChatLLMResponse(
                message="Trading",
                trades=[
                    ChatTrade(ticker="AAPL", side="sell", quantity=5),  # no shares
                    ChatTrade(ticker="MSFT", side="buy", quantity=1),  # ok
                ],
            )
        ),
    )

    resp = await client.post("/api/chat", json={"message": "trade"})
    data = resp.json()
    assert len(data["trades"]) == 2
    assert data["trades"][0]["error"] == "insufficient shares"
    assert "error" not in data["trades"][1]
    assert data["trades"][1]["ticker"] == "MSFT"

    assert db.get_position("MSFT") is not None
    assert db.get_position("AAPL") is None


@pytest.mark.asyncio
async def test_watchlist_auto_execution(client, monkeypatch):
    import app.llm as llm

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        llm.litellm,
        "completion",
        _fake_completion(
            ChatLLMResponse(
                message="Updating watchlist",
                watchlist_changes=[
                    ChatWatchlistChange(ticker="PYPL", action="add"),
                    ChatWatchlistChange(ticker="AAPL", action="remove"),
                    ChatWatchlistChange(ticker="ZZZZ", action="remove"),  # not present
                ],
            )
        ),
    )

    resp = await client.post("/api/chat", json={"message": "watchlist"})
    changes = resp.json()["watchlist_changes"]
    assert changes[0] == {"ticker": "PYPL", "action": "add"}
    assert changes[1] == {"ticker": "AAPL", "action": "remove"}
    assert "error" in changes[2]

    tickers = {row["ticker"] for row in db.list_watchlist()}
    assert "PYPL" in tickers
    assert "AAPL" not in tickers


@pytest.mark.asyncio
async def test_malformed_response_fallback(client, monkeypatch):
    import app.llm as llm

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def _boom(*args, **kwargs):
        raise RuntimeError("upstream exploded")

    monkeypatch.setattr(llm.litellm, "completion", _boom)

    resp = await client.post("/api/chat", json={"message": "hi"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"].startswith("Sorry, I had trouble")
    assert data["trades"] == []
    assert data["watchlist_changes"] == []


@pytest.mark.asyncio
async def test_mock_mode_buy(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    # First watchlist ticker is AAPL (seed order), price it so the buy fills.
    first = db.list_watchlist()[0]["ticker"]
    set_price(client, first, 20.0)

    resp = await client.post("/api/chat", json={"message": "please BUY something"})
    data = resp.json()
    assert len(data["trades"]) == 1
    assert data["trades"][0]["ticker"] == first
    assert data["trades"][0]["side"] == "buy"
    assert data["trades"][0]["quantity"] == 1
    assert db.get_position(first) is not None


@pytest.mark.asyncio
async def test_mock_mode_sell(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    set_price(client, "AAPL", 100.0)
    db.upsert_position("AAPL", 10, 90.0)

    resp = await client.post("/api/chat", json={"message": "sell it"})
    data = resp.json()
    assert len(data["trades"]) == 1
    assert data["trades"][0]["ticker"] == "AAPL"
    assert data["trades"][0]["side"] == "sell"


@pytest.mark.asyncio
async def test_mock_mode_sell_nothing_held(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")

    resp = await client.post("/api/chat", json={"message": "sell everything"})
    data = resp.json()
    assert data["trades"] == []
    assert "no positions" in data["message"].lower()


@pytest.mark.asyncio
async def test_mock_mode_other(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")

    resp = await client.post("/api/chat", json={"message": "how am I doing?"})
    data = resp.json()
    assert data["trades"] == []
    assert data["watchlist_changes"] == []
    assert "Ticker" in data["message"]


@pytest.mark.asyncio
async def test_actions_persisted_to_history(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    first = db.list_watchlist()[0]["ticker"]
    set_price(client, first, 20.0)

    await client.post("/api/chat", json={"message": "buy now"})
    stored = db.list_chat_messages()[-1]
    assert stored["role"] == "assistant"
    assert stored["actions"]["trades"][0]["ticker"] == first
    assert isinstance(stored["actions"], dict)
    json.dumps(stored["actions"])  # round-trips cleanly
