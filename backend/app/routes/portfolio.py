from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import db
from app.market_data.cache import PriceCache

router = APIRouter()

_SELL_EPSILON = 1e-9


class TradeError(Exception):
    """Raised when a trade fails validation (bad side/quantity, no price,
    insufficient cash or shares). Callers translate this into an HTTP 400 or an
    inline chat error as appropriate."""


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str


def execute_trade_core(
    ticker: str, quantity: float, side: str, cache: PriceCache
) -> dict:
    """Validate and execute a single market trade against the current price.

    Raises TradeError on any validation failure. On success returns
    {"trade": {...}, "cash_balance": float, "position": {...} | None}.
    """
    ticker = ticker.strip().upper()
    side = side.strip().lower()

    if side not in ("buy", "sell"):
        raise TradeError("side must be 'buy' or 'sell'")
    if quantity <= 0:
        raise TradeError("quantity must be greater than 0")

    update = cache.get(ticker)
    if update is None:
        raise TradeError(f"no price available for {ticker}")
    price = update.price

    profile = db.get_profile()
    cash_balance = profile["cash_balance"]
    existing = db.get_position(ticker)

    if side == "buy":
        cost = quantity * price
        if cost > cash_balance:
            raise TradeError("insufficient cash")
        new_cash = cash_balance - cost
        if existing:
            old_qty = existing["quantity"]
            old_avg = existing["avg_cost"]
            new_qty = old_qty + quantity
            new_avg = (old_qty * old_avg + quantity * price) / new_qty
        else:
            new_qty = quantity
            new_avg = price
        position = db.upsert_position(ticker, new_qty, new_avg)
    else:  # sell
        owned = existing["quantity"] if existing else 0.0
        if quantity > owned:
            raise TradeError("insufficient shares")
        new_cash = cash_balance + quantity * price
        remaining = owned - quantity
        if remaining < _SELL_EPSILON:
            db.delete_position(ticker)
            position = None
        else:
            position = db.upsert_position(ticker, remaining, existing["avg_cost"])

    db.update_cash_balance(new_cash)
    trade = db.record_trade(ticker, side, quantity, price)
    db.record_snapshot(compute_total_value(cache))

    position_view = build_position_view(position, cache) if position else None
    return {
        "trade": {
            "id": trade["id"],
            "ticker": trade["ticker"],
            "side": trade["side"],
            "quantity": trade["quantity"],
            "price": trade["price"],
            "executed_at": trade["executed_at"],
        },
        "cash_balance": new_cash,
        "position": position_view,
    }


def _current_price(cache: PriceCache, ticker: str, fallback: float) -> float:
    update = cache.get(ticker)
    return update.price if update is not None else fallback


def build_position_view(position: dict, cache: PriceCache) -> dict:
    quantity = position["quantity"]
    avg_cost = position["avg_cost"]
    current_price = _current_price(cache, position["ticker"], avg_cost)
    unrealized_pnl = (current_price - avg_cost) * quantity
    unrealized_pnl_pct = (
        (current_price - avg_cost) / avg_cost * 100 if avg_cost else 0.0
    )
    return {
        "ticker": position["ticker"],
        "quantity": quantity,
        "avg_cost": avg_cost,
        "current_price": current_price,
        "unrealized_pnl": round(unrealized_pnl, 2),
        "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
    }


def compute_total_value(cache: PriceCache) -> float:
    profile = db.get_profile()
    cash_balance = profile["cash_balance"] if profile else 0.0
    positions_value = sum(
        p["quantity"] * _current_price(cache, p["ticker"], p["avg_cost"])
        for p in db.list_positions()
    )
    return cash_balance + positions_value


def build_portfolio(cache: PriceCache) -> dict:
    profile = db.get_profile()
    cash_balance = profile["cash_balance"] if profile else 0.0
    positions = [build_position_view(p, cache) for p in db.list_positions()]
    positions_value = sum(p["quantity"] * p["current_price"] for p in positions)
    total_unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)
    return {
        "cash_balance": cash_balance,
        "positions": positions,
        "total_value": round(cash_balance + positions_value, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
    }


@router.get("/api/portfolio")
async def get_portfolio(request: Request) -> dict:
    return build_portfolio(request.app.state.price_cache)


@router.get("/api/portfolio/history")
async def get_portfolio_history() -> list[dict]:
    return [
        {"total_value": s["total_value"], "recorded_at": s["recorded_at"]}
        for s in db.list_snapshots()
    ]


@router.post("/api/portfolio/trade")
async def execute_trade(request: Request, body: TradeRequest) -> dict:
    cache: PriceCache = request.app.state.price_cache
    try:
        return execute_trade_core(body.ticker, body.quantity, body.side, cache)
    except TradeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
