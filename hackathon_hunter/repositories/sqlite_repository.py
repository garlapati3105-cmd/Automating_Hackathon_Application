"""
SQLite implementation of AbstractHackathonRepository.

Design decisions:
- The database file and parent directories are created automatically on
  the first call to initialize().
- Deduplication is enforced at the database level via a UNIQUE constraint
  on the `url` column. INSERT OR IGNORE is used so that a duplicate never
  raises an exception — the return value indicates whether the row was new.
- Every query uses parameterized statements (no string interpolation).
- Connections are opened per-operation and closed immediately to keep the
  module thread-safe and easy to test.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.repositories.base import AbstractHackathonRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS hackathons (
    id         INTEGER   PRIMARY KEY AUTOINCREMENT,
    platform   TEXT      NOT NULL,
    name       TEXT      NOT NULL,
    url        TEXT      NOT NULL UNIQUE,
    location   TEXT,
    deadline   TEXT,
    is_online  INTEGER,
    status     TEXT      DEFAULT 'NEW',
    first_seen TIMESTAMP,
    raw_json   TEXT
);
"""

_INSERT_SQL = """
INSERT OR IGNORE INTO hackathons
    (platform, name, url, location, deadline, is_online, status, first_seen, raw_json)
VALUES
    (:platform, :name, :url, :location, :deadline, :is_online, :status, :first_seen, :raw_json);
"""

_EXISTS_SQL = "SELECT 1 FROM hackathons WHERE url = ? LIMIT 1;"

_LIST_ALL_SQL = """
SELECT id, platform, name, url, location, deadline, is_online,
       status, first_seen, raw_json
FROM hackathons
ORDER BY first_seen DESC;
"""


class SQLiteHackathonRepository(AbstractHackathonRepository):
    """
    SQLite-backed repository for hackathon persistence.

    Args:
        db_path: Path to the SQLite database file.
                 Defaults to ``data/hackathons.db`` (project-root-relative).
    """

    def __init__(self, db_path: str = "data/hackathons.db") -> None:
        self._db_path = Path(db_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with row_factory set to sqlite3.Row."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # AbstractHackathonRepository interface
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """
        Create the database file, its parent directory, and the schema
        table if they do not already exist.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()
        logger.debug("Database initialised at %s", self._db_path.resolve())

    def exists(self, url: str) -> bool:
        """Return True if a hackathon with *url* is already stored."""
        with self._connect() as conn:
            row = conn.execute(_EXISTS_SQL, (url,)).fetchone()
        return row is not None

    def add(self, hackathon: Hackathon) -> bool:
        """
        Insert a hackathon into the database.

        Uses ``INSERT OR IGNORE`` so duplicate URLs are silently skipped.

        Returns:
            True  — inserted (new hackathon).
            False — skipped (URL already existed).

        Raises:
            RuntimeError: On unexpected database errors.
        """
        try:
            with self._connect() as conn:
                cursor = conn.execute(_INSERT_SQL, hackathon.to_db_dict())
                conn.commit()
                inserted = cursor.rowcount > 0

            if inserted:
                logger.debug("Inserted new hackathon: %s", hackathon.url)
            else:
                logger.debug("Duplicate skipped: %s", hackathon.url)

            return inserted

        except sqlite3.Error as exc:
            logger.error(
                "Database error while inserting hackathon '%s': %s",
                hackathon.url,
                exc,
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to insert hackathon '{hackathon.url}': {exc}"
            ) from exc

    def list_all(self) -> list[Hackathon]:
        """Return all hackathons ordered by first_seen descending."""
        with self._connect() as conn:
            rows = conn.execute(_LIST_ALL_SQL).fetchall()
        return [Hackathon.from_db_row(dict(row)) for row in rows]
