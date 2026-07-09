import json

import pytest

from app import db


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the data layer at an isolated temp SQLite file per test."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    db.reset_connection()
    yield
    db.reset_connection()


# --- schema + seed ---------------------------------------------------------


def test_schema_created_on_fresh_db(fresh_db):
    conn = db.get_connection()
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
    } <= names


def test_seed_default_profile(fresh_db):
    profile = db.get_profile()
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0
    assert profile["created_at"]


def test_seed_default_watchlist(fresh_db):
    tickers = {row["ticker"] for row in db.list_watchlist()}
    assert tickers == {
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
        "NVDA", "META", "JPM", "V", "NFLX",
    }


def test_init_is_idempotent(fresh_db):
    db.get_connection()
    db.update_cash_balance(500.0)
    # Re-run initialization against the same file.
    db.reset_connection()
    conn = db.get_connection()
    db._initialize(conn)
    assert len(db.list_watchlist()) == 10
    # Existing cash balance is preserved, not reset to the seed default.
    assert db.get_profile()["cash_balance"] == 500.0


# --- profile ---------------------------------------------------------------


def test_update_cash_balance(fresh_db):
    updated = db.update_cash_balance(7500.25)
    assert updated["cash_balance"] == 7500.25
    assert db.get_profile()["cash_balance"] == 7500.25


# --- watchlist -------------------------------------------------------------


def test_add_watchlist(fresh_db):
    row = db.add_watchlist("pypl")
    assert row["ticker"] == "PYPL"
    assert "PYPL" in {r["ticker"] for r in db.list_watchlist()}


def test_add_watchlist_duplicate_is_noop(fresh_db):
    before = len(db.list_watchlist())
    db.add_watchlist("AAPL")
    assert len(db.list_watchlist()) == before


def test_watchlist_unique_constraint(fresh_db):
    import sqlite3

    conn = db.get_connection()
    db.get_profile()  # ensure init
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            ("x", "default", "AAPL", "2026-01-01"),
        )


def test_remove_watchlist(fresh_db):
    assert db.remove_watchlist("AAPL") is True
    assert "AAPL" not in {r["ticker"] for r in db.list_watchlist()}


def test_remove_watchlist_missing_returns_false(fresh_db):
    assert db.remove_watchlist("ZZZZ") is False


# --- positions -------------------------------------------------------------


def test_upsert_position_insert_then_update(fresh_db):
    db.upsert_position("AAPL", 10.0, 190.0)
    pos = db.get_position("AAPL")
    assert pos["quantity"] == 10.0
    assert pos["avg_cost"] == 190.0

    db.upsert_position("AAPL", 15.0, 192.0)
    pos = db.get_position("AAPL")
    assert pos["quantity"] == 15.0
    assert pos["avg_cost"] == 192.0
    # Still exactly one row for the ticker.
    assert len([p for p in db.list_positions() if p["ticker"] == "AAPL"]) == 1


def test_get_position_missing_returns_none(fresh_db):
    assert db.get_position("AAPL") is None


def test_list_positions(fresh_db):
    db.upsert_position("AAPL", 1.0, 100.0)
    db.upsert_position("MSFT", 2.0, 200.0)
    tickers = {p["ticker"] for p in db.list_positions()}
    assert tickers == {"AAPL", "MSFT"}


def test_delete_position(fresh_db):
    db.upsert_position("AAPL", 1.0, 100.0)
    assert db.delete_position("AAPL") is True
    assert db.get_position("AAPL") is None
    assert db.delete_position("AAPL") is False


def test_positions_unique_constraint(fresh_db):
    import sqlite3

    conn = db.get_connection()
    db.upsert_position("AAPL", 1.0, 100.0)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO positions "
            "(id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("x", "default", "AAPL", 5.0, 5.0, "2026-01-01"),
        )


# --- trades ----------------------------------------------------------------


def test_record_and_list_trades(fresh_db):
    db.record_trade("AAPL", "buy", 10.0, 190.0)
    db.record_trade("AAPL", "sell", 5.0, 195.0)
    trades = db.list_trades()
    assert len(trades) == 2
    # Most recent first.
    assert trades[0]["side"] == "sell"
    assert trades[1]["side"] == "buy"


def test_list_trades_limit(fresh_db):
    for _ in range(5):
        db.record_trade("AAPL", "buy", 1.0, 100.0)
    assert len(db.list_trades(limit=3)) == 3


# --- snapshots -------------------------------------------------------------


def test_record_and_list_snapshots_ascending(fresh_db):
    db.record_snapshot(10000.0)
    db.record_snapshot(10500.0)
    db.record_snapshot(9800.0)
    snaps = db.list_snapshots()
    values = [s["total_value"] for s in snaps]
    assert values == [10000.0, 10500.0, 9800.0]


def test_list_snapshots_limit_returns_most_recent_ascending(fresh_db):
    for v in [1.0, 2.0, 3.0, 4.0]:
        db.record_snapshot(v)
    snaps = db.list_snapshots(limit=2)
    assert [s["total_value"] for s in snaps] == [3.0, 4.0]


# --- chat messages ---------------------------------------------------------


def test_add_chat_message_user_no_actions(fresh_db):
    msg = db.add_chat_message("user", "hello")
    assert msg["role"] == "user"
    assert msg["content"] == "hello"
    assert msg["actions"] is None


def test_add_chat_message_with_actions_roundtrip(fresh_db):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}
    msg = db.add_chat_message("assistant", "done", actions=actions)
    assert msg["actions"] == actions
    # Stored as JSON text.
    conn = db.get_connection()
    raw = conn.execute(
        "SELECT actions FROM chat_messages WHERE id = ?", (msg["id"],)
    ).fetchone()["actions"]
    assert json.loads(raw) == actions


def test_list_chat_messages_oldest_first(fresh_db):
    db.add_chat_message("user", "first")
    db.add_chat_message("assistant", "second")
    db.add_chat_message("user", "third")
    msgs = db.list_chat_messages()
    assert [m["content"] for m in msgs] == ["first", "second", "third"]


def test_list_chat_messages_limit_keeps_most_recent(fresh_db):
    for i in range(5):
        db.add_chat_message("user", f"m{i}")
    msgs = db.list_chat_messages(limit=2)
    assert [m["content"] for m in msgs] == ["m3", "m4"]
