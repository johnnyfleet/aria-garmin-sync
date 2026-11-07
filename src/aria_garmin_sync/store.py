"""SQLite record of synced readings and alert state."""

import sqlite3
from datetime import UTC, datetime

from . import config
from .readings import Reading

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id          TEXT PRIMARY KEY,
    weighed_at  TEXT NOT NULL,
    weight_kg   REAL NOT NULL,
    fat_pct     REAL,
    outcome     TEXT NOT NULL,   -- 'uploaded' or 'already_in_garmin'
    synced_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS state (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class Store:
    def __init__(self, path=None) -> None:
        path = path or config.STATE_DB
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def is_synced(self, reading_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM readings WHERE id = ?", (reading_id,)).fetchone() is not None

    def record(self, r: Reading, outcome: str) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO readings VALUES (?, ?, ?, ?, ?, ?)",
                (r.id, r.time.isoformat(), r.weight_kg, r.fat_pct, outcome, datetime.now(UTC).isoformat()),
            )

    def get(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str | None) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, value))
