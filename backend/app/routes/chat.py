"""Chat endpoint: routes a user message through the LLM, auto-executes any
trades and watchlist changes it returns, persists the exchange, and returns the
conversational reply plus the executed/errored actions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app import db
from app.llm import generate_chat_response
from app.market_data.cache import PriceCache
from app.routes.portfolio import TradeError, execute_trade_core
from app.routes.watchlist import _sync_provider

logger = logging.getLogger(__name__)

router = APIRouter()

_FALLBACK_MESSAGE = "Sorry, I had trouble processing that — could you rephrase?"


class ChatRequest(BaseModel):
    message: str


def _execute_trades(trades, cache: PriceCache) -> list[dict]:
    """Run each trade through execute_trade_core in order. Successes carry the
    executed fields; failures carry an error string and do not abort the rest."""
    executed: list[dict] = []
    for trade in trades:
        try:
            result = execute_trade_core(
                trade.ticker, trade.quantity, trade.side, cache
            )
            t = result["trade"]
            executed.append(
                {
                    "ticker": t["ticker"],
                    "side": t["side"],
                    "quantity": t["quantity"],
                    "price": t["price"],
                    "executed_at": t["executed_at"],
                }
            )
        except TradeError as e:
            executed.append(
                {
                    "ticker": trade.ticker.strip().upper(),
                    "side": trade.side.strip().lower(),
                    "quantity": trade.quantity,
                    "error": str(e),
                }
            )
    return executed


def _apply_watchlist_changes(changes, request: Request) -> list[dict]:
    applied: list[dict] = []
    for change in changes:
        ticker = change.ticker.strip().upper()
        action = change.action.strip().lower()
        entry: dict = {"ticker": ticker, "action": action}
        if action == "add":
            db.add_watchlist(ticker)
            _sync_provider(request)
        elif action == "remove":
            removed = db.remove_watchlist(ticker)
            if not removed:
                entry["error"] = f"{ticker} not in watchlist"
            else:
                _sync_provider(request)
        else:
            entry["error"] = f"unknown action '{action}'"
        applied.append(entry)
    return applied


@router.post("/api/chat")
async def chat(request: Request, body: ChatRequest) -> dict:
    cache: PriceCache = request.app.state.price_cache

    db.add_chat_message("user", body.message)

    try:
        llm_response = await generate_chat_response(body.message, cache)
    except Exception:
        logger.exception("LLM chat request failed")
        return {"message": _FALLBACK_MESSAGE, "trades": [], "watchlist_changes": []}

    trades = _execute_trades(llm_response.trades, cache)
    watchlist_changes = _apply_watchlist_changes(llm_response.watchlist_changes, request)

    db.add_chat_message(
        "assistant",
        llm_response.message,
        actions={"trades": trades, "watchlist_changes": watchlist_changes},
    )

    return {
        "message": llm_response.message,
        "trades": trades,
        "watchlist_changes": watchlist_changes,
    }
