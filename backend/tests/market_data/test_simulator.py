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
    gbm_step,
)


class FixedRNG:
    def __init__(self, z):
        self._z = z

    def gauss(self, mu, sigma):
        return self._z


def test_gbm_step_matches_formula_for_fixed_shock():
    price, mu, sigma, dt = 100.0, 0.10, 0.20, 0.25
    z = 0.5
    result = gbm_step(price, mu, sigma, dt, FixedRNG(z))
    expected = price * math.exp((mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * z)
    assert result == pytest.approx(expected)


def test_gbm_step_zero_volatility_is_pure_drift():
    price, mu, dt = 100.0, 0.10, 1.0
    result = gbm_step(price, mu, 0.0, dt, FixedRNG(z=3.0))
    assert result == pytest.approx(price * math.exp(mu * dt))


def test_gbm_step_is_deterministic_for_a_given_seed():
    a = gbm_step(100.0, 0.1, 0.3, 0.01, random.Random(42))
    b = gbm_step(100.0, 0.1, 0.3, 0.01, random.Random(42))
    assert a == b


def test_gbm_step_statistical_moments_match_theory():
    mu, sigma, dt = 0.15, 0.40, 0.01
    rng = random.Random(2024)
    n = 200_000
    price = 100.0
    log_returns = []
    for _ in range(n):
        new_price = gbm_step(price, mu, sigma, dt, rng)
        log_returns.append(math.log(new_price / price))
        price = new_price

    sample_mean = statistics.fmean(log_returns)
    sample_var = statistics.pvariance(log_returns)

    theoretical_mean = (mu - 0.5 * sigma**2) * dt
    theoretical_var = sigma**2 * dt

    se_mean = sigma * math.sqrt(dt) / math.sqrt(n)
    assert abs(sample_mean - theoretical_mean) < 8 * se_mean
    assert sample_var == pytest.approx(theoretical_var, rel=0.05)


def test_set_tickers_seeds_known_ticker_from_seed_params():
    provider = SimulatorProvider(cache=PriceCache())
    provider.set_tickers({"AAPL"})
    state = provider._state["AAPL"]
    assert state.price == SEED_PARAMS["AAPL"].seed_price
    assert state.open_price == SEED_PARAMS["AAPL"].seed_price
    assert state.params is SEED_PARAMS["AAPL"]


def test_set_tickers_seeds_unknown_ticker_from_default_params():
    provider = SimulatorProvider(cache=PriceCache())
    provider.set_tickers({"ZZZZ"})
    state = provider._state["ZZZZ"]
    assert state.price == DEFAULT_PARAMS.seed_price
    assert state.params is DEFAULT_PARAMS


def test_set_tickers_drops_removed_tickers():
    provider = SimulatorProvider(cache=PriceCache())
    provider.set_tickers({"AAPL", "MSFT"})
    provider.set_tickers({"AAPL"})
    assert set(provider._state) == {"AAPL"}


def test_set_tickers_preserves_state_for_retained_tickers():
    provider = SimulatorProvider(cache=PriceCache(), seed=1)
    provider.set_tickers({"AAPL"})
    provider._tick()
    ticked_price = provider._state["AAPL"].price
    provider.set_tickers({"AAPL", "MSFT"})
    assert provider._state["AAPL"].price == ticked_price


def test_tick_writes_to_cache_for_all_tracked_tickers():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1)
    provider.set_tickers({"AAPL", "MSFT"})
    provider._tick()
    assert cache.get("AAPL") is not None
    assert cache.get("MSFT") is not None


def test_tick_sets_previous_price_to_prior_tick_price():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1)
    provider.set_tickers({"AAPL"})
    first_seed_price = SEED_PARAMS["AAPL"].seed_price
    provider._tick()
    first_update = cache.get("AAPL")
    assert first_update.previous_price == first_seed_price
    provider._tick()
    second_update = cache.get("AAPL")
    assert second_update.previous_price == first_update.price


def test_tick_keeps_open_price_fixed_across_ticks():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1)
    provider.set_tickers({"AAPL"})
    provider._tick()
    provider._tick()
    provider._tick()
    assert cache.get("AAPL").open_price == SEED_PARAMS["AAPL"].seed_price


async def test_start_populates_cache_after_first_tick():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1, tick_interval_seconds=0.01)
    provider.set_tickers({"AAPL"})
    await provider.start()
    try:
        await asyncio.sleep(0)
        assert cache.get("AAPL") is not None
    finally:
        await provider.stop()


async def test_stop_cancels_the_background_task():
    cache = PriceCache()
    provider = SimulatorProvider(cache=cache, seed=1, tick_interval_seconds=0.01)
    provider.set_tickers({"AAPL"})
    await provider.start()
    await provider.stop()
    assert provider._task is None


async def test_stop_without_start_is_a_no_op():
    provider = SimulatorProvider(cache=PriceCache())
    await provider.stop()
