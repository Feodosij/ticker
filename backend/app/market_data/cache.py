from .base import PriceUpdate


class PriceCache:
    """In-memory latest-price store. Single writer (the active provider),
    many readers (SSE connections). No locking: FastAPI's asyncio event loop
    is single-threaded and every method here is synchronous (no `await`
    between the read and the write), so there's no interleaving to guard
    against.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}

    def set_price(self, update: PriceUpdate) -> None:
        self._prices[update.ticker] = update

    def get(self, ticker: str) -> PriceUpdate | None:
        return self._prices.get(ticker)

    def get_many(self, tickers: set[str]) -> list[PriceUpdate]:
        return [self._prices[t] for t in tickers if t in self._prices]

    def all_tickers(self) -> set[str]:
        return set(self._prices)
