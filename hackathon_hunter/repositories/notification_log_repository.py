"""
Notification Log Repository.

Tracks which hackathons have already triggered notifications on each channel,
preventing duplicate notifications across multiple scraper runs.

Schema (created on first call to initialize()):
    notification_log (
        id              INTEGER   PRIMARY KEY AUTOINCREMENT,
        url             TEXT      NOT NULL,
        channel         TEXT      NOT NULL,   -- 'email', 'telegram', etc.
        hackathon_name  TEXT,
        notified_at     TIMESTAMP NOT NULL
    )
    UNIQUE constraint on (url, channel) — one row per hackathon-channel pair.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackathon_hunter.models.hackathon import Hackathon

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS notification_log (
    id             INTEGER   PRIMARY KEY AUTOINCREMENT,
    url            TEXT      NOT NULL,
    channel        TEXT      NOT NULL,
    hackathon_name TEXT,
    notified_at    TIMESTAMP NOT NULL,
    UNIQUE(url, channel)
);
"""


class NotificationLogRepository:
    """
    Persists which hackathon URLs have already been notified per channel.

    Args:
        db_path: Path to the SQLite database file.
                 Uses the same file as SQLiteHackathonRepository so both
                 tables live in one database.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Create the notification_log table if it does not exist."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()
        logger.debug("[notif-log] Table ready at %s", self._db_path)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_notified(self, url: str, channel: str) -> bool:
        """Return True if this URL has already been notified via ``channel``."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM notification_log WHERE url = ? AND channel = ? LIMIT 1",
                (url, channel),
            ).fetchone()
        return row is not None

    def filter_unnotified(
        self,
        hackathons: list[Hackathon],
        channel: str,
    ) -> list[Hackathon]:
        """
        Return only the hackathons that have NOT yet been notified via ``channel``.

        Uses a single query with an IN clause for efficiency.
        """
        if not hackathons:
            return []

        urls = [h.url for h in hackathons]
        placeholders = ",".join("?" * len(urls))
        with self._connect() as conn:
            already_notified_rows = conn.execute(
                f"SELECT url FROM notification_log "
                f"WHERE channel = ? AND url IN ({placeholders})",
                [channel, *urls],
            ).fetchall()

        already_notified = {row[0] for row in already_notified_rows}
        pending = [h for h in hackathons if h.url not in already_notified]

        logger.debug(
            "[notif-log] channel=%s total=%d already_notified=%d pending=%d",
            channel,
            len(hackathons),
            len(already_notified),
            len(pending),
        )
        return pending

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def mark_notified(self, hackathons: list[Hackathon], channel: str) -> int:
        """
        Record that these hackathons were successfully notified via ``channel``.

        Uses INSERT OR IGNORE so re-marking an already-recorded URL is safe.

        Returns:
            Number of rows actually inserted (excludes already-existing rows).
        """
        if not hackathons:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        rows = [(h.url, channel, h.name, now) for h in hackathons]

        inserted = 0
        with self._connect() as conn:
            for row in rows:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO notification_log "
                    "(url, channel, hackathon_name, notified_at) VALUES (?, ?, ?, ?)",
                    row,
                )
                inserted += cursor.rowcount
            conn.commit()

        logger.debug(
            "[notif-log] mark_notified channel=%s inserted=%d/%d",
            channel,
            inserted,
            len(hackathons),
        )
        return inserted

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)
