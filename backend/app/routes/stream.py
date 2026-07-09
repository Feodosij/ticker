import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app import db
from app.market_data.cache import PriceCache

router = APIRouter()

TICK_INTERVAL_SECONDS = 0.5


@router.get("/api/stream/prices")
async def stream_prices(request: Request) -> EventSourceResponse:
    cache: PriceCache = request.app.state.price_cache

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            tickers = {row["ticker"] for row in db.list_watchlist()}
            payload = [
                {
                    "ticker": u.ticker,
                    "price": u.price,
                    "previous_price": u.previous_price,
                    "change_direction": u.change_direction,
                    "change_pct": round(u.change_pct, 2),
                    "timestamp": u.timestamp.isoformat(),
                }
                for u in cache.get_many(tickers)
            ]
            yield {"event": "price_update", "data": json.dumps(payload)}
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    return EventSourceResponse(event_generator())
