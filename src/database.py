"""A tiny SQLite store for the searches people run.

Every time the user clicks "Find Destinations" we save their settings and the
top result. This gives the app a simple search history (which also ticks the
brief's "consider adding a database" box) without needing any server.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

# Keep the database next to the other data files, at data/holiday_planner.db.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "holiday_planner.db"


def _connect() -> sqlite3.Connection:
    """Open a connection to the SQLite database file.

    Takes nothing. Returns an open sqlite3.Connection. The file (and its parent
    folder) is created automatically if it doesn't exist yet.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Create the search_history table if it isn't there already.

    Takes nothing and returns nothing. Safe to call on every app start.
    """
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                min_temp REAL NOT NULL,
                max_budget INTEGER NOT NULL,
                priorities TEXT NOT NULL,
                trip_duration TEXT NOT NULL,
                top_destination TEXT,
                score INTEGER
            )
            """
        )


def insert_search(
    min_temp: float,
    max_budget: int,
    priorities: list[str],
    trip_duration: str,
    top_destination: str | None,
    score: int | None,
) -> None:
    """Save one search to the history table.

    Takes the user's settings plus the winning destination and its score (which
    may be None if nothing matched). The priorities list is stored as a simple
    comma-joined string. Returns nothing.
    """
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO search_history
                (timestamp, min_temp, max_budget, priorities,
                 trip_duration, top_destination, score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                min_temp,
                max_budget,
                ", ".join(priorities),
                trip_duration,
                top_destination,
                score,
            ),
        )


def fetch_recent(limit: int = 5) -> list[dict]:
    """Return the most recent searches, newest first.

    Takes the maximum number of rows to return. Returns a list of dicts, one per
    search, with keys matching the table columns.
    """
    with _connect() as conn:
        # row_factory lets us read columns by name instead of by position.
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM search_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
