import asyncio
import math
import random
import statistics

import pytest

from app.market_data.cache import PriceCache
from app.market_data.simulator import (
    DEFAULT_PARAMS,
    SEED_PARAMS,
    SimulatorProvider,
    TickerParams,
    gbm_step,
)


def test_gbm_step_is_deterministic_for_a_given_seed():
    rng_a = random.Random(42)
    rng_b = random.Random(42)

    result_a = gbm_step(100.0, mu=0.10, sigma=0.30, dt_years=0.001, rng=rng_a)
    result_b = gbm_step(100.0, mu=0.10, sigma=0.30, dt_years=0.001, rng=rng_b)

    assert result_a == result_b


def test_gbm_step_matches_closed_form_for_a_known_draw():
    rng = random.Random(7)
    z = rng.gauss(0.0, 1.0)  # consume the same draw gbm_step will consume

    rng_for_step = random.Random(7)
    price = 100.0
    mu, sigma, dt = 0.10, 0.30, 0.002
    result = gbm_step(price, mu, sigma, dt, rng_for_step)

    expected = price * math.exp((mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * z)
    assert result == pytest.approx(expected)


def test_gbm_step_zero_volatility_follows_pure_drift():
    rng = random.Random(1)
    price = 100.0
    dt = 1.0  # one full year, to make the drift obvious
    result = gbm_step(price, mu=0.10, sigma=0.0, dt_years=dt, rng=rng)
    assert result == pytest.approx(price * math.exp(0.10 * dt))


def test_gbm_step_statistical_mean_and_variance_converge_to_theoretical():
    rng = random.Random(123)
    price = 100.0
    mu, sigma, dt = 0.10, 0.30, 0.01
    log_returns = []
    for _ in range(20_000):
        new_price = gbm_step(price, mu, sigma, dt, rng)
        log_returns.append(math.log(new_price / price))

    sample_mean = statistics.mean(log_returns)
    sample_stdev = statistics.stdev(log_returns)

    expected_mean = (mu - 0.5 * sigma**2) * dt
    expected_stdev = sigma * math.sqrt(dt)

    assert sample_mean == pytest.approx(expected_mean, abs=0.005)
    assert sample_stdev == pytest.approx(expected_stdev, rel=0.05)


def test_set_tickers_seeds_known_tickers_from_seed_params():
    provider = SimulatorProvider(cache=PriceCache(), seed=1)
    provider.set_tickers({"AAPL"})
    provider.tick()

    update = provider._cache.get("AAPL")
    assert update is not None
    assert update.open_price == SEED_PARAMS["AAPL"].seed_price


def test_set_tickers_seeds_unknown_tickers_from_default_params():
    provider = SimulatorProvider(cache=PriceCache(), seed=1)
    provider.set_tickers({"ZZZZ"})
    provider.tick()

    update = provider._cache.get("ZZZZ")
    assert update is not None
    assert update.open_price == DEFAULT_PARAMS.seed_price


def test_set_tickers_is_idempotent_and_preserves_existing_price_progress():
    provider = SimulatorProvider(cache=PriceCache(), seed=1)
    provider.set_tickers({"AAPL"})
    provider.tick()
    price_after_one_tick = provider._cache.get("AAPL").price

    # Re-calling set_tickers with the same ticker must not reset its state.
    provider.set_tickers({"AAPL"})
    assert provider._state["AAPL"].price == price_after_one_tick


def test_set_tickers_drops_tickers_no_longer_tracked():
    provider = SimulatorProvider(cache=PriceCache(), seed=1)
    provider.set_tickers({"AAPL", "GOOGL"})
    provider.set_tickers({"AAPL"})

    assert "GOOGL" not in provider._state
    assert "AAPL" in provider._state


def test_tick_writes_a_price_update_to_the_cache_for_every_tracked_ticker():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1)
    provider.set_tickers({"AAPL", "MSFT"})

    provider.tick()

    assert cache.get("AAPL") is not None
    assert cache.get("MSFT") is not None


def test_tick_updates_previous_price_to_prior_tick_price():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1)
    provider.set_tickers({"AAPL"})

    provider.tick()
    first_price = cache.get("AAPL").price
    provider.tick()
    second_update = cache.get("AAPL")

    assert second_update.previous_price == first_price


def test_tick_with_no_tracked_tickers_is_a_no_op():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1)
    provider.tick()
    assert cache.all_tickers() == set()


async def test_start_populates_cache_and_stop_cancels_cleanly():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1)
    provider.set_tickers({"AAPL"})

    await provider.start()
    try:
        # Wait past at least one tick interval for the background loop to run.
        for _ in range(50):
            if cache.get("AAPL") is not None:
                break
            await asyncio.sleep(0.05)
    finally:
        await provider.stop()

    assert cache.get("AAPL") is not None
    assert provider._task is None


async def test_start_picks_up_tickers_added_after_start():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1)

    await provider.start()
    try:
        provider.set_tickers({"NVDA"})
        for _ in range(50):
            if cache.get("NVDA") is not None:
                break
            await asyncio.sleep(0.05)
    finally:
        await provider.stop()

    assert cache.get("NVDA") is not None


def test_ticker_params_are_distinct_per_symbol():
    # Sanity-check the seed data itself: every default ticker should have a
    # distinct volatility so the watchlist doesn't look uniform on screen.
    sigmas = [params.sigma for params in SEED_PARAMS.values()]
    assert len(set(sigmas)) > 1


def test_ticker_params_dataclass_holds_provided_values():
    params = TickerParams(seed_price=50.0, mu=0.05, sigma=0.20)
    assert params.seed_price == 50.0
    assert params.mu == 0.05
    assert params.sigma == 0.20
