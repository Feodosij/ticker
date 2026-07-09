from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app import db
from app.market_data.cache import PriceCache

router = APIRouter()


class WatchlistRequest(BaseModel):
    ticker: str


def build_watchlist_entry(row: dict, cache: PriceCache) -> dict:
    update = cache.get(row["ticker"])
    if update is None:
        return {
            "ticker": row["ticker"],
            "price": None,
            "previous_price": None,
            "change_direction": None,
            "change_pct": None,
            "added_at": row["added_at"],
        }
    return {
        "ticker": row["ticker"],
        "price": update.price,
        "previous_price": update.previous_price,
        "change_direction": update.change_direction,
        "change_pct": round(update.change_pct, 2),
        "added_at": row["added_at"],
    }


def _sync_provider(request: Request) -> None:
    tickers = {row["ticker"] for row in db.list_watchlist()}
    request.app.state.provider.set_tickers(tickers)


@router.get("/api/watchlist")
async def get_watchlist(request: Request) -> list[dict]:
    cache: PriceCache = request.app.state.price_cache
    return [build_watchlist_entry(row, cache) for row in db.list_watchlist()]


@router.post("/api/watchlist", status_code=201)
async def add_to_watchlist(request: Request, body: WatchlistRequest, response: Response) -> dict:
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    already_present = any(row["ticker"] == ticker for row in db.list_watchlist())
    row = db.add_watchlist(ticker)
    _sync_provider(request)

    if already_present:
        response.status_code = 200
    return build_watchlist_entry(row, request.app.state.price_cache)


@router.delete("/api/watchlist/{ticker}", status_code=204)
async def remove_from_watchlist(request: Request, ticker: str) -> Response:
    removed = db.remove_watchlist(ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker.strip().upper()} not in watchlist")
    _sync_provider(request)
    return Response(status_code=204)
