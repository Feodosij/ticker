"""SQLite data-access layer for Ticker.

A thin repository over stdlib `sqlite3`. The database is lazily created and
seeded on first use. All access goes through a single process-wide connection
(the app is a single-process asyncio server, so synchronous sqlite calls are
fine). Every query is parameterized; ids are UUIDs and timestamps are ISO-8601.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0
DEFAULT_WATCHLIST = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "finally.db"

_connection: sqlite3.Connection | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def _resolve_db_target() -> str:
    """Runtime DB location. Overridable via DB_PATH (e.g. ':memory:' or a tmp
    file for tests); defaults to <project-root>/db/finally.db."""
    override = os.environ.get("DB_PATH")
    return override if override else str(_DEFAULT_DB_PATH)


def _create_connection() -> sqlite3.Connection:
    target = _resolve_db_target()
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_PATH.read_text())
    _seed(conn)
    conn.commit()


def _seed(conn: sqlite3.Connection) -> None:
    """Insert default profile and watchlist. Idempotent: INSERT OR IGNORE means
    a second call adds nothing and never resets an existing cash balance."""
    now = _now()
    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) "
        "VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
    )
    for ticker in DEFAULT_WATCHLIST:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) "
            "VALUES (?, ?, ?, ?)",
            (_uuid(), DEFAULT_USER_ID, ticker, now),
        )


def get_connection() -> sqlite3.Connection:
    """Return the process-wide connection, creating and seeding the DB on first
    use."""
    global _connection
    if _connection is None:
        _connection = _create_connection()
        _initialize(_connection)
    return _connection


def reset_connection() -> None:
    """Close and drop the cached connection. Intended for tests that repoint
    DB_PATH between cases."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


# --- users_profile ---------------------------------------------------------


def get_profile(user_id: str = DEFAULT_USER_ID) -> dict | None:
    row = get_connection().execute(
        "SELECT * FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def update_cash_balance(cash_balance: float, user_id: str = DEFAULT_USER_ID) -> dict | None:
    conn = get_connection()
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (cash_balance, user_id),
    )
    conn.commit()
    return get_profile(user_id)


# --- watchlist -------------------------------------------------------------


def list_watchlist(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = get_connection().execute(
        "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at, ticker",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> dict | None:
    """Add a ticker. No-op if already present (UNIQUE user_id,ticker). Returns
    the row for the ticker."""
    ticker = ticker.strip().upper()
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) "
        "VALUES (?, ?, ?, ?)",
        (_uuid(), user_id, ticker, _now()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    return dict(row) if row else None


def remove_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    ticker = ticker.strip().upper()
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    conn.commit()
    return cur.rowcount > 0


# --- positions -------------------------------------------------------------


def list_positions(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = get_connection().execute(
        "SELECT * FROM positions WHERE user_id = ? ORDER BY ticker",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> dict | None:
    ticker = ticker.strip().upper()
    row = get_connection().execute(
        "SELECT * FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    return dict(row) if row else None


def upsert_position(
    ticker: str,
    quantity: float,
    avg_cost: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Insert or update the holding for (user_id, ticker)."""
    ticker = ticker.strip().upper()
    conn = get_connection()
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (user_id, ticker) DO UPDATE SET "
        "quantity = excluded.quantity, avg_cost = excluded.avg_cost, "
        "updated_at = excluded.updated_at",
        (_uuid(), user_id, ticker, quantity, avg_cost, _now()),
    )
    conn.commit()
    return get_position(ticker, user_id)  # type: ignore[return-value]


def delete_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Remove a holding (e.g. after selling the full quantity)."""
    ticker = ticker.strip().upper()
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    conn.commit()
    return cur.rowcount > 0


# --- trades ----------------------------------------------------------------


def record_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    ticker = ticker.strip().upper()
    trade_id = _uuid()
    conn = get_connection()
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (trade_id, user_id, ticker, side, quantity, price, _now()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    return dict(row)


def list_trades(user_id: str = DEFAULT_USER_ID, limit: int | None = None) -> list[dict]:
    """Trade history, most recent first."""
    sql = "SELECT * FROM trades WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC"
    params: tuple = (user_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (user_id, limit)
    rows = get_connection().execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# --- portfolio_snapshots ---------------------------------------------------


def record_snapshot(total_value: float, user_id: str = DEFAULT_USER_ID) -> dict:
    snap_id = _uuid()
    conn = get_connection()
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (snap_id, user_id, total_value, _now()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM portfolio_snapshots WHERE id = ?", (snap_id,)
    ).fetchone()
    return dict(row)


def list_snapshots(user_id: str = DEFAULT_USER_ID, limit: int | None = None) -> list[dict]:
    """Portfolio value over time, oldest first (chart order). When limited,
    returns the most recent `limit` snapshots, still oldest-first."""
    if limit is None:
        rows = get_connection().execute(
            "SELECT * FROM portfolio_snapshots WHERE user_id = ? "
            "ORDER BY recorded_at, rowid",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    rows = get_connection().execute(
        "SELECT * FROM portfolio_snapshots WHERE user_id = ? "
        "ORDER BY recorded_at DESC, rowid DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


# --- chat_messages ---------------------------------------------------------


def _message_row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["actions"] = json.loads(d["actions"]) if d["actions"] is not None else None
    return d


def add_chat_message(
    role: str,
    content: str,
    actions: object | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Append a chat message. `actions` (any JSON-serializable value, or None)
    is stored as a JSON string and returned parsed."""
    msg_id = _uuid()
    actions_json = json.dumps(actions) if actions is not None else None
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, user_id, role, content, actions_json, _now()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM chat_messages WHERE id = ?", (msg_id,)
    ).fetchone()
    return _message_row_to_dict(row)


def list_chat_messages(user_id: str = DEFAULT_USER_ID, limit: int = 50) -> list[dict]:
    """The most recent `limit` messages, oldest-first (conversation order)."""
    rows = get_connection().execute(
        "SELECT * FROM chat_messages WHERE user_id = ? "
        "ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [_message_row_to_dict(r) for r in reversed(rows)]
