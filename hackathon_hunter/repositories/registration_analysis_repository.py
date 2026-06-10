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
    Manages persistence of hackathon registration readiness analyses.
    """

    def __init__(self, db_path: str = "data/hackathons.db") -> None:
        self._db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Create the registration_analysis table if it does not exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
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
            conn.commit()
        logger.debug("registration_analysis table ready at %s", self._db_path)

    def save_placeholder(self, url: str, name: str) -> str:
        """
        Creates a placeholder analysis record for a newly discovered hackathon.
        Defaults analysis_status to 'NOT_ANALYZED'.
        Returns the generated approval_token.
        """
        now = datetime.now(timezone.utc).isoformat()
        token = uuid.uuid4().hex
        with self._connect() as conn:
            # Only insert if it doesn't already exist
            row = conn.execute("SELECT approval_token FROM registration_analysis WHERE url = ?", (url,)).fetchone()
            if row:
                return row["approval_token"]

            conn.execute("""
            INSERT INTO registration_analysis (
                url, hackathon_name, profile_field_count, question_field_count,
                team_field_count, consent_field_count, unknown_field_count,
                automation_score, requires_human_review, classification,
                automation_recommendation, approval_status, analysis_status,
                approval_token, created_at, updated_at
            ) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 1, 'LOW', 'MANUAL_ONLY', 'PENDING', 'NOT_ANALYZED', ?, ?, ?)
            """, (url, name, token, now, now))
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
        token = uuid.uuid4().hex
        with self._connect() as conn:
            row = conn.execute("SELECT approval_status, approval_token FROM registration_analysis WHERE url = ?", (url,)).fetchone()
            if row:
                # Keep existing approval status & token
                status = row["approval_status"]
                ret_token = row["approval_token"]
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
                    approval_token, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ANALYZED', ?, ?, ?)
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
        token = uuid.uuid4().hex
        with self._connect() as conn:
            row = conn.execute("SELECT approval_status, approval_token FROM registration_analysis WHERE url = ?", (url,)).fetchone()
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
                    approval_token, created_at, updated_at
                ) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 1, 'LOW', 'MANUAL_ONLY', 'PENDING', 'FAILED', ?, ?, ?)
                """, (url, hackathon_name or "", ret_token, now, now))
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
        """Retrieves analysis record for a URL."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM registration_analysis WHERE url = ?", (url,)).fetchone()
            if row:
                return dict(row)
            return None

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        """Lists all analyses with a specific approval status."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM registration_analysis WHERE approval_status = ?", (status,)).fetchall()
            return [dict(r) for r in rows]
