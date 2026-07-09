import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.market_data import PriceCache, create_market_data_provider
from app.routes import chat, health, portfolio, stream, watchlist
from app.routes.portfolio import compute_total_value

SNAPSHOT_INTERVAL_SECONDS = 30
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


async def _snapshot_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
        db.record_snapshot(compute_total_value(app.state.price_cache))


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    provider = create_market_data_provider(cache)
    provider.set_tickers({row["ticker"] for row in db.list_watchlist()})
    await provider.start()

    app.state.price_cache = cache
    app.state.provider = provider

    snapshot_task = asyncio.create_task(_snapshot_loop(app))
    try:
        yield
    finally:
        snapshot_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await snapshot_task
        await provider.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)

app.include_router(health.router)
app.include_router(watchlist.router)
app.include_router(portfolio.router)
app.include_router(stream.router)
app.include_router(chat.router)

if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
