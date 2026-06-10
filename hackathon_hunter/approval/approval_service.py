from __future__ import annotations

import logging
from datetime import datetime, timezone
from hackathon_hunter.repositories.registration_analysis_repository import (
    RegistrationAnalysisRepository,
)
from hackathon_hunter.approval.token_manager import TokenManager

logger = logging.getLogger(__name__)


class TokenValidationError(ValueError):
    """Raised when token validation fails (unregistered or expired token)."""
    pass


class ApprovalService:
    """
    Implements approval workflow transitions (approve, reject, status lookup)
    with security validation and logging.
    """

    def __init__(self, repository: RegistrationAnalysisRepository) -> None:
        self._repo = repository

    def approve(self, token: str, notes: str | None = None) -> dict:
        """Approve a registration by token, logging transaction history."""
        with self._repo._connect() as conn:
            row = conn.execute("SELECT * FROM registration_analysis WHERE approval_token = ?", (token,)).fetchone()
            if not row:
                raise TokenValidationError("Token not found or invalid.")

            record = dict(row)
            
            # Check for expiration dynamically
            if TokenManager.is_expired(record.get("token_expires_at")):
                # Transition status to EXPIRED
                self._repo.update_status(record["url"], "EXPIRED")
                self._repo.add_history_log(token, "EXPIRE", "Token checked and found expired during approval attempt.")
                raise TokenValidationError("Token has expired.")

            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
            UPDATE registration_analysis
            SET approval_status = 'APPROVED',
                approved_at = ?,
                approval_notes = ?,
                updated_at = ?
            WHERE approval_token = ?
            """, (now, notes, now, token))
            conn.commit()

        # Log history
        self._repo.add_history_log(token, "APPROVE", notes)

        updated = self._repo.get_analysis(record["url"])
        return updated

    def reject(self, token: str, notes: str | None = None) -> dict:
        """Reject a registration by token, logging transaction history."""
        with self._repo._connect() as conn:
            row = conn.execute("SELECT * FROM registration_analysis WHERE approval_token = ?", (token,)).fetchone()
            if not row:
                raise TokenValidationError("Token not found or invalid.")

            record = dict(row)

            # Check for expiration dynamically
            if TokenManager.is_expired(record.get("token_expires_at")):
                # Transition status to EXPIRED
                self._repo.update_status(record["url"], "EXPIRED")
                self._repo.add_history_log(token, "EXPIRE", "Token checked and found expired during rejection attempt.")
                raise TokenValidationError("Token has expired.")

            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
            UPDATE registration_analysis
            SET approval_status = 'REJECTED',
                rejected_at = ?,
                approval_notes = ?,
                updated_at = ?
            WHERE approval_token = ?
            """, (now, notes, now, token))
            conn.commit()

        # Log history
        self._repo.add_history_log(token, "REJECT", notes)

        updated = self._repo.get_analysis(record["url"])
        return updated

    def get_status(self, token: str) -> dict:
        """Retrieve status details for a token, transitioning expired tokens if needed."""
        with self._repo._connect() as conn:
            row = conn.execute("SELECT * FROM registration_analysis WHERE approval_token = ?", (token,)).fetchone()
            if not row:
                raise TokenValidationError("Token not found or invalid.")
            
            record = dict(row)
            url = record["url"]

        # get_analysis in repository dynamically checks PENDING expiration and transitions it
        updated = self._repo.get_analysis(url)
        return updated
