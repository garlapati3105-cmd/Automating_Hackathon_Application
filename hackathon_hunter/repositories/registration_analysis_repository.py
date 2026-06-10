from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RegistrationAnalysisRepository:
    """
    Manages persistence of hackathon registration readiness analyses and approval logs.
    """

    def __init__(self, db_path: str = "data/hackathons.db") -> None:
        self._db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Create tables and execute migrations if columns are missing."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            # Create base table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS registration_analysis (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                url                    TEXT NOT NULL UNIQUE,
                hackathon_name         TEXT,
                profile_field_count    INTEGER NOT NULL,
                question_field_count   INTEGER NOT NULL,
                team_field_count       INTEGER NOT NULL,
                consent_field_count    INTEGER NOT NULL,
                unknown_field_count    INTEGER NOT NULL,
                automation_score       INTEGER NOT NULL,
                requires_human_review  INTEGER NOT NULL,
                classification         TEXT NOT NULL,
                automation_recommendation TEXT NOT NULL,
                approval_status        TEXT NOT NULL,
                analysis_status        TEXT NOT NULL,
                approval_token         TEXT NOT NULL,
                created_at             TIMESTAMP NOT NULL,
                updated_at             TIMESTAMP NOT NULL
            );
            """)

            # Create approval history table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS approval_history (
                id         INTEGER   PRIMARY KEY AUTOINCREMENT,
                token      TEXT      NOT NULL,
                action     TEXT      NOT NULL,
                timestamp  TIMESTAMP NOT NULL,
                notes      TEXT
            );
            """)
            conn.commit()

            # Schema migrations check
            cursor = conn.execute("PRAGMA table_info(registration_analysis)")
            columns = [row["name"] for row in cursor.fetchall()]

            new_cols = {
                "approved_at": "TIMESTAMP",
                "rejected_at": "TIMESTAMP",
                "approval_notes": "TEXT",
                "token_expires_at": "TIMESTAMP"
            }

            for col_name, col_type in new_cols.items():
                if col_name not in columns:
                    logger.info("Migrating registration_analysis table: adding column %s", col_name)
                    conn.execute(f"ALTER TABLE registration_analysis ADD COLUMN {col_name} {col_type};")
                    conn.commit()

        logger.debug("registration_analysis and approval_history tables ready at %s", self._db_path)

    def add_history_log(self, token: str, action: str, notes: str | None = None) -> None:
        """Log an action to approval_history table."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("""
            INSERT INTO approval_history (token, action, timestamp, notes)
            VALUES (?, ?, ?, ?)
            """, (token, action, now, notes))
            conn.commit()

    def save_placeholder(self, url: str, name: str) -> str:
        """
        Creates a placeholder analysis record for a newly discovered hackathon.
        Defaults analysis_status to 'NOT_ANALYZED'.
        Returns the generated approval_token.
        """
        now = datetime.now(timezone.utc).isoformat()
        from hackathon_hunter.approval.token_manager import TokenManager
        token, expiration = TokenManager.generate_token()

        with self._connect() as conn:
            row = conn.execute("SELECT approval_token FROM registration_analysis WHERE url = ?", (url,)).fetchone()
            if row:
                return row["approval_token"]

            conn.execute("""
            INSERT INTO registration_analysis (
                url, hackathon_name, profile_field_count, question_field_count,
                team_field_count, consent_field_count, unknown_field_count,
                automation_score, requires_human_review, classification,
                automation_recommendation, approval_status, analysis_status,
                approval_token, token_expires_at, created_at, updated_at
            ) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 1, 'LOW', 'MANUAL_ONLY', 'PENDING', 'NOT_ANALYZED', ?, ?, ?, ?)
            """, (url, name, token, expiration, now, now))
            conn.commit()
        return token

    def save_analysis(
        self,
        url: str,
        hackathon_name: str,
        profile_count: int,
        question_count: int,
        team_count: int,
        consent_count: int,
        unknown_count: int,
        score: int,
        requires_human_review: bool,
        classification: str,
        recommendation: str,
        approval_status: str = "PENDING",
    ) -> str:
        """
        Saves or updates a complete analysis result, setting status to 'ANALYZED'.
        Returns the approval_token for the row.
        """
        now = datetime.now(timezone.utc).isoformat()
        from hackathon_hunter.approval.token_manager import TokenManager
        token, expiration = TokenManager.generate_token()

        with self._connect() as conn:
            row = conn.execute("SELECT approval_status, approval_token, token_expires_at FROM registration_analysis WHERE url = ?", (url,)).fetchone()
            if row:
                status = row["approval_status"]
                ret_token = row["approval_token"]
                ret_expires = row["token_expires_at"] or expiration
                conn.execute("""
                UPDATE registration_analysis
                SET hackathon_name = ?,
                    profile_field_count = ?,
                    question_field_count = ?,
                    team_field_count = ?,
                    consent_field_count = ?,
                    unknown_field_count = ?,
                    automation_score = ?,
                    requires_human_review = ?,
                    classification = ?,
                    automation_recommendation = ?,
                    approval_status = ?,
                    analysis_status = 'ANALYZED',
                    token_expires_at = ?,
                    updated_at = ?
                WHERE url = ?
                """, (
                    hackathon_name,
                    profile_count,
                    question_count,
                    team_count,
                    consent_count,
                    unknown_count,
                    score,
                    int(requires_human_review),
                    classification,
                    recommendation,
                    status,
                    ret_expires,
                    now,
                    url,
                ))
            else:
                ret_token = token
                conn.execute("""
                INSERT INTO registration_analysis (
                    url, hackathon_name, profile_field_count, question_field_count,
                    team_field_count, consent_field_count, unknown_field_count,
                    automation_score, requires_human_review, classification,
                    automation_recommendation, approval_status, analysis_status,
                    approval_token, token_expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ANALYZED', ?, ?, ?, ?)
                """, (
                    url,
                    hackathon_name,
                    profile_count,
                    question_count,
                    team_count,
                    consent_count,
                    unknown_count,
                    score,
                    int(requires_human_review),
                    classification,
                    recommendation,
                    approval_status,
                    ret_token,
                    expiration,
                    now,
                    now,
                ))
            conn.commit()
        return ret_token

    def save_failed_analysis(self, url: str, hackathon_name: str = None) -> str:
        """
        Sets or creates a record with analysis_status 'FAILED'.
        Returns the approval_token for the row.
        """
        now = datetime.now(timezone.utc).isoformat()
        from hackathon_hunter.approval.token_manager import TokenManager
        token, expiration = TokenManager.generate_token()

        with self._connect() as conn:
            row = conn.execute("SELECT approval_status, approval_token, token_expires_at FROM registration_analysis WHERE url = ?", (url,)).fetchone()
            if row:
                ret_token = row["approval_token"]
                conn.execute("""
                UPDATE registration_analysis
                SET analysis_status = 'FAILED',
                    updated_at = ?
                WHERE url = ?
                """, (now, url))
            else:
                ret_token = token
                conn.execute("""
                INSERT INTO registration_analysis (
                    url, hackathon_name, profile_field_count, question_field_count,
                    team_field_count, consent_field_count, unknown_field_count,
                    automation_score, requires_human_review, classification,
                    automation_recommendation, approval_status, analysis_status,
                    approval_token, token_expires_at, created_at, updated_at
                ) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 1, 'LOW', 'MANUAL_ONLY', 'PENDING', 'FAILED', ?, ?, ?, ?)
                """, (url, hackathon_name or "", ret_token, expiration, now, now))
            conn.commit()
        return ret_token

    def update_status(self, url: str, status: str) -> None:
        """Updates the approval status for a hackathon analysis."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("""
            UPDATE registration_analysis
            SET approval_status = ?, updated_at = ?
            WHERE url = ?
            """, (status, now, url))
            conn.commit()

    def get_analysis(self, url: str) -> Optional[dict[str, Any]]:
        """Retrieves analysis record for a URL. Transitions expired pending analyses."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM registration_analysis WHERE url = ?", (url,)).fetchone()
            if not row:
                return None
            record = dict(row)
            
            # Check and transition status to EXPIRED if applicable
            if record.get("approval_status") == "PENDING":
                from hackathon_hunter.approval.token_manager import TokenManager
                if TokenManager.is_expired(record.get("token_expires_at")):
                    self.update_status(url, "EXPIRED")
                    record["approval_status"] = "EXPIRED"

            return record

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        """Lists all analyses with a specific approval status. Forces dynamic expiration checks."""
        # Force status transition for all PENDING expired rows first
        if status.upper() == "EXPIRED" or status.upper() == "PENDING":
            with self._connect() as conn:
                pending_rows = conn.execute("SELECT url, token_expires_at FROM registration_analysis WHERE approval_status = 'PENDING'").fetchall()
                from hackathon_hunter.approval.token_manager import TokenManager
                for row in pending_rows:
                    if TokenManager.is_expired(row["token_expires_at"]):
                        self.update_status(row["url"], "EXPIRED")

        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM registration_analysis WHERE approval_status = ?", (status.upper(),)).fetchall()
            return [dict(r) for r in rows]
