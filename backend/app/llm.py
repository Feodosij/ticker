"""LLM integration for the Ticker chat assistant.

Wraps the LiteLLM -> OpenRouter call with a structured-output schema, builds the
system/context prompt from the user's live portfolio and watchlist, and provides
a deterministic mock (LLM_MOCK=true) for fast, free, reproducible E2E tests.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import litellm
from pydantic import BaseModel, Field

from app import db
from app.market_data.cache import PriceCache
from app.routes.portfolio import build_portfolio
from app.routes.watchlist import build_watchlist_entry

logger = logging.getLogger(__name__)

OPENROUTER_MODEL = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

MOCK_DEFAULT_MESSAGE = (
    "I'm Ticker, your AI trading assistant. Ask me about your portfolio or "
    "tell me what to trade."
)

SYSTEM_PROMPT = """You are Ticker, an AI trading assistant embedded in a \
simulated trading workstation. You help the user manage a virtual portfolio.

Your responsibilities:
- Analyze portfolio composition, risk concentration, and P&L.
- Suggest trades with clear, data-driven reasoning.
- Execute trades when the user asks or agrees, by populating the `trades` array.
- Manage the watchlist proactively via the `watchlist_changes` array.
- Be concise and data-driven.

Rules:
- `quantity` in a trade is always a SHARE COUNT (whole or fractional), never a \
dollar amount. If the user asks for a dollar-denominated trade (e.g. "buy $500 \
of AAPL"), do NOT convert dollars to shares yourself — instead ask them to \
specify a share quantity, and leave `trades` empty.
- Only add trades/watchlist_changes you actually intend to execute now.
- Always respond with valid JSON matching the required schema."""


class ChatTrade(BaseModel):
    ticker: str
    side: str  # "buy" | "sell"
    quantity: float


class ChatWatchlistChange(BaseModel):
    ticker: str
    action: str  # "add" | "remove"


class ChatLLMResponse(BaseModel):
    message: str
    trades: list[ChatTrade] = Field(default_factory=list)
    watchlist_changes: list[ChatWatchlistChange] = Field(default_factory=list)


def _mock_is_enabled() -> bool:
    return os.getenv("LLM_MOCK", "false").lower() == "true"


def _build_context(cache: PriceCache) -> str:
    portfolio = build_portfolio(cache)
    watchlist = [build_watchlist_entry(row, cache) for row in db.list_watchlist()]
    context = {
        "cash_balance": portfolio["cash_balance"],
        "total_value": portfolio["total_value"],
        "total_unrealized_pnl": portfolio["total_unrealized_pnl"],
        "positions": portfolio["positions"],
        "watchlist": [
            {"ticker": w["ticker"], "price": w["price"], "change_pct": w["change_pct"]}
            for w in watchlist
        ],
    }
    return json.dumps(context)


def _build_messages(user_message: str, cache: PriceCache) -> list[dict]:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": "Current portfolio and watchlist context:\n"
            + _build_context(cache),
        },
    ]
    for msg in db.list_chat_messages(limit=20):
        role = "assistant" if msg["role"] == "assistant" else "user"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


def _mock_response(user_message: str, cache: PriceCache) -> ChatLLMResponse:
    """Deterministic keyword-matched response used when LLM_MOCK=true.

    - contains "buy" -> buy 1 share of the first watchlist ticker (AAPL if empty)
    - contains "sell" -> sell 1 share of the first held position (canned message
      if nothing is held)
    - otherwise -> a fixed canned message with no actions
    """
    text = user_message.lower()
    if "buy" in text:
        watchlist = db.list_watchlist()
        ticker = watchlist[0]["ticker"] if watchlist else "AAPL"
        return ChatLLMResponse(
            message=f"Buying 1 share of {ticker}.",
            trades=[ChatTrade(ticker=ticker, side="buy", quantity=1)],
        )
    if "sell" in text:
        positions = db.list_positions()
        if positions:
            ticker = positions[0]["ticker"]
            return ChatLLMResponse(
                message=f"Selling 1 share of {ticker}.",
                trades=[ChatTrade(ticker=ticker, side="sell", quantity=1)],
            )
        return ChatLLMResponse(message="You have no positions to sell.")
    return ChatLLMResponse(message=MOCK_DEFAULT_MESSAGE)


async def generate_chat_response(user_message: str, cache: PriceCache) -> ChatLLMResponse:
    """Produce a structured chat response. Uses the deterministic mock when
    LLM_MOCK=true; otherwise calls the LLM via LiteLLM/OpenRouter. Raises on any
    LLM/parse failure — the caller is responsible for the graceful fallback.

    Context-building does synchronous sqlite reads, so it stays on the calling
    (event loop) thread — the sqlite connection is thread-affine. Only the
    actual blocking network call is offloaded to a worker thread, so a slow
    LLM round-trip doesn't stall the event loop (SSE price stream, market-data
    background task) for the whole app.
    """
    if _mock_is_enabled():
        return _mock_response(user_message, cache)

    messages = _build_messages(user_message, cache)
    response = await asyncio.to_thread(
        litellm.completion,
        model=OPENROUTER_MODEL,
        api_base=OPENROUTER_API_BASE,
        api_key=os.environ["OPENROUTER_API_KEY"],
        messages=messages,
        response_format=ChatLLMResponse,
    )
    return ChatLLMResponse.model_validate_json(response.choices[0].message.content)
