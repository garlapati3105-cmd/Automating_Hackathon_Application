from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta


class TokenManager:
    """
    Generates and validates secure token credentials for the approval flow.
    """

    @staticmethod
    def generate_token(expires_in_days: int = 7) -> tuple[str, str]:
        """
        Generates a secure UUID4 token and its expiration ISO timestamp.
        """
        token = str(uuid.uuid4())
        expiration = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()
        return token, expiration

    @staticmethod
    def is_expired(expiration_timestamp: str | None) -> bool:
        """
        Validates token expiration. Returns True if expired, False otherwise.
        """
        if not expiration_timestamp:
            return False
        try:
            exp_dt = datetime.fromisoformat(expiration_timestamp)
            return datetime.now(timezone.utc) > exp_dt
        except Exception:
            return True
