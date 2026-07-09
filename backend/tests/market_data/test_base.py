import dataclasses
from datetime import datetime, timezone

import pytest

from app.market_data.base import PriceUpdate

NOW = datetime(2026, 1, 5, 15, 30, tzinfo=timezone.utc)


def _update(price: float, previous_price: float, open_price: float = 100.0) -> PriceUpdate:
    return PriceUpdate(
        ticker="AAPL",
        price=price,
        previous_price=previous_price,
        open_price=open_price,
        timestamp=NOW,
    )


def test_change_direction_up():
    assert _update(price=101.0, previous_price=100.0).change_direction == "up"


def test_change_direction_down():
    assert _update(price=99.0, previous_price=100.0).change_direction == "down"


def test_change_direction_flat():
    assert _update(price=100.0, previous_price=100.0).change_direction == "flat"


def test_change_pct_positive():
    update = _update(price=110.0, previous_price=105.0, open_price=100.0)
    assert update.change_pct == 10.0


def test_change_pct_negative():
    update = _update(price=95.0, previous_price=99.0, open_price=100.0)
    assert update.change_pct == -5.0


def test_change_pct_zero_open_price_does_not_divide_by_zero():
    update = _update(price=10.0, previous_price=9.0, open_price=0.0)
    assert update.change_pct == 0.0


def test_price_update_is_frozen():
    update = _update(price=100.0, previous_price=99.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        update.price = 200.0  # type: ignore[misc]
