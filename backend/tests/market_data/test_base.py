from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.market_data.base import PriceUpdate


def make_update(**overrides):
    defaults = dict(
        ticker="AAPL",
        price=100.0,
        previous_price=100.0,
        open_price=100.0,
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return PriceUpdate(**defaults)


def test_change_direction_up():
    update = make_update(price=101.0, previous_price=100.0)
    assert update.change_direction == "up"


def test_change_direction_down():
    update = make_update(price=99.0, previous_price=100.0)
    assert update.change_direction == "down"


def test_change_direction_flat():
    update = make_update(price=100.0, previous_price=100.0)
    assert update.change_direction == "flat"


def test_change_pct_positive():
    update = make_update(price=110.0, open_price=100.0)
    assert update.change_pct == pytest.approx(10.0)


def test_change_pct_negative():
    update = make_update(price=90.0, open_price=100.0)
    assert update.change_pct == pytest.approx(-10.0)


def test_change_pct_zero_open_price_is_safe():
    update = make_update(price=50.0, open_price=0.0)
    assert update.change_pct == 0.0


def test_price_update_is_frozen():
    update = make_update()
    with pytest.raises(FrozenInstanceError):
        update.price = 200.0
