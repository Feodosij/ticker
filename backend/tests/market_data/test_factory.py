from app.market_data import create_market_data_provider
from app.market_data.cache import PriceCache
from app.market_data.massive import MassiveProvider
from app.market_data.simulator import SimulatorProvider


def test_no_api_key_selects_simulator(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    provider = create_market_data_provider(PriceCache())
    assert isinstance(provider, SimulatorProvider)


def test_empty_api_key_selects_simulator(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "")
    provider = create_market_data_provider(PriceCache())
    assert isinstance(provider, SimulatorProvider)


def test_whitespace_only_api_key_selects_simulator(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "   ")
    provider = create_market_data_provider(PriceCache())
    assert isinstance(provider, SimulatorProvider)


def test_api_key_present_selects_massive(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "some-real-key")
    provider = create_market_data_provider(PriceCache())
    assert isinstance(provider, MassiveProvider)
