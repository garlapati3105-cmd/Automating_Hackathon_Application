from __future__ import annotations

import logging
from enum import Enum

from hackathon_hunter.repositories.registration_analysis_repository import (
    RegistrationAnalysisRepository,
)

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


class ApprovalEngine:
    """
    Manages approval statuses for hackathon registration configurations.
    Enforces safe execution boundary (does not submit forms or interact with buttons).
    """

    def __init__(self, repository: RegistrationAnalysisRepository) -> None:
        self._repo = repository

    def approve(self, url: str) -> None:
        """Set approval status of hackathon at URL to APPROVED."""
        logger.info("Approving hackathon registration automation for URL: %s", url)
        self._repo.update_status(url, ApprovalStatus.APPROVED.value)

    def reject(self, url: str) -> None:
        """Set approval status of hackathon at URL to REJECTED."""
        logger.info("Rejecting hackathon registration automation for URL: %s", url)
        self._repo.update_status(url, ApprovalStatus.REJECTED.value)

    def get_status(self, url: str) -> str:
        """Retrieve approval status of hackathon at URL."""
        analysis = self._repo.get_analysis(url)
        if analysis:
            return analysis.get("approval_status", ApprovalStatus.PENDING.value)
        return ApprovalStatus.PENDING.value
