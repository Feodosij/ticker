from app.market_data import create_market_data_provider
from app.market_data.cache import PriceCache
from app.market_data.massive import MassiveProvider
from app.market_data.simulator import SimulatorProvider


def test_returns_simulator_when_api_key_unset(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    provider = create_market_data_provider(PriceCache())
    assert isinstance(provider, SimulatorProvider)


def test_returns_simulator_when_api_key_blank(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "   ")
    provider = create_market_data_provider(PriceCache())
    assert isinstance(provider, SimulatorProvider)


def test_returns_massive_when_api_key_set(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "secret-key")
    provider = create_market_data_provider(PriceCache())
    assert isinstance(provider, MassiveProvider)
