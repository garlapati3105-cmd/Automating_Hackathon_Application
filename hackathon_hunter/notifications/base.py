"""
BaseNotifier — Abstract base class for all notification channels.

To add a new channel (e.g. Telegram, Discord, Slack):
  1. Subclass BaseNotifier in a new module.
  2. Implement ``send_batch()`` and ``channel_name``.
  3. Register an instance in NotificationManager via main.py.

No other files need to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackathon_hunter.models.hackathon import Hackathon


class BaseNotifier(ABC):
    """
    Abstract notification channel.

    Each concrete subclass represents one delivery mechanism
    (email, Telegram, Discord, webhooks, etc.).

    All implementations must be fault-tolerant: ``send_batch()`` should
    catch its own exceptions and never propagate them to the caller.
    The scraper pipeline must not be interrupted by a notification failure.
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """
        Human-readable channel identifier used for logging and dedup keys.

        Examples: ``"email"``, ``"telegram"``, ``"discord"``
        Must be lowercase, stable across runs, and unique per notifier type.
        """
        ...

    @abstractmethod
    def send_batch(self, hackathons: list[Hackathon]) -> bool:
        """
        Send a single summary notification covering all hackathons in the batch.

        Args:
            hackathons: Non-empty list of newly discovered Hackathon objects
                        that have NOT yet been notified via this channel.
                        The list has already been deduplicated by
                        NotificationManager before this method is called.

        Returns:
            True if the notification was sent successfully, False otherwise.
            Implementations should log errors and return False rather than raise.
        """
        ...
