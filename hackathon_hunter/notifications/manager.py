"""
NotificationManager — Orchestrates multiple notification channels.

Responsibilities:
  1. Filter out hackathons already notified on each channel (dedup).
  2. Call send_batch() on every registered notifier.
  3. Mark successfully notified hackathons in the notification_log.

Design notes:
  - If a notifier fails, it is skipped; other notifiers still run.
  - The notification_log is updated only on success, so a failed send
    will be retried on the next run.
  - Adding a new channel (Telegram, Discord) requires only:
      a. A new BaseNotifier subclass.
      b. Appending an instance to the notifiers list in main.py.
    No changes to this file are needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hackathon_hunter.config import settings
from hackathon_hunter.notifications.base import BaseNotifier
from hackathon_hunter.notifications.filters import (
    is_india_hackathon,
    is_hyderabad_hackathon,
    hackathon_priority_key,
)
from hackathon_hunter.repositories.notification_log_repository import (
    NotificationLogRepository,
)

if TYPE_CHECKING:
    from hackathon_hunter.models.hackathon import Hackathon

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Coordinates dedup-aware notification delivery across multiple channels.

    Args:
        notifiers: List of BaseNotifier instances (email, telegram, …).
        log_repo:  NotificationLogRepository for tracking sent notifications.
    """

    def __init__(
        self,
        notifiers: list[BaseNotifier],
        log_repo: NotificationLogRepository,
    ) -> None:
        self._notifiers = notifiers
        self._log_repo = log_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def notify_batch(self, hackathons: list[Hackathon]) -> dict[str, int]:
        """
        Send notifications for all provided hackathons via every channel.

        Each channel independently deduplicates against the notification_log.
        Channels that fail do not affect other channels.

        Args:
            hackathons: All newly inserted Hackathon objects from this run.

        Returns:
            Dict mapping channel_name → count of hackathons successfully notified.
            Example: {"email": 5, "telegram": 0}
        """
        if not hackathons:
            logger.debug("[manager] notify_batch called with empty list — nothing to do.")
            return {}

        original_count = len(hackathons)

        # Apply location filtering if configured
        if settings.LOCATION_FILTER == "india":
            filtered = []
            for h in hackathons:
                is_online = h.is_online or (h.location and "online" in h.location.lower()) or h.location is None
                if is_online and settings.INCLUDE_ONLINE:
                    filtered.append(h)
                elif is_india_hackathon(h.location) or is_hyderabad_hackathon(h.location):
                    filtered.append(h)
            hackathons = filtered
            logger.info(
                "[manager] Location filter 'india' active. Match count: %d/%d",
                len(hackathons),
                original_count,
            )

        if not hackathons:
            logger.info("[manager] No hackathons matched the location filters after filtering.")
            return {}

        # Sort hackathons by priority (Hyderabad -> Other India -> Online -> Others)
        priority_city = getattr(settings, "PRIORITY_CITY", "hyderabad")
        hackathons = sorted(hackathons, key=lambda h: hackathon_priority_key(h, priority_city=priority_city))


        if not self._notifiers:
            logger.debug("[manager] No notifiers registered — skipping.")
            return {}

        logger.info(
            "[manager] notify_batch: %d hackathon(s), %d channel(s): %s",
            len(hackathons),
            len(self._notifiers),
            ", ".join(n.channel_name for n in self._notifiers),
        )

        results: dict[str, int] = {}

        for notifier in self._notifiers:
            channel = notifier.channel_name
            try:
                count = self._dispatch(notifier, hackathons)
                results[channel] = count
            except Exception as exc:  # noqa: BLE001
                # Defensive: notifiers should not raise, but guard here too.
                logger.error(
                    "[manager] Unexpected error from notifier '%s': %s",
                    channel,
                    exc,
                    exc_info=True,
                )
                results[channel] = 0

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch(self, notifier: BaseNotifier, hackathons: list[Hackathon]) -> int:
        """
        Deduplicate, send, and mark for a single notifier.

        Returns:
            Number of hackathons that were newly notified (0 on failure).
        """
        channel = notifier.channel_name

        # 1. Filter out already-notified hackathons for this channel
        pending = self._log_repo.filter_unnotified(hackathons, channel)

        if not pending:
            logger.info("[manager] [%s] All %d hackathon(s) already notified — skipping.", channel, len(hackathons))
            return 0

        logger.info("[manager] [%s] Sending batch: %d hackathon(s).", channel, len(pending))

        # 2. Send the batch notification
        success = notifier.send_batch(pending)

        if not success:
            logger.warning(
                "[manager] [%s] send_batch() reported failure — "
                "notification_log NOT updated (will retry next run).",
                channel,
            )
            return 0

        # 3. Record in notification_log only on success
        inserted = self._log_repo.mark_notified(pending, channel)
        logger.info(
            "[manager] [%s] Notification log updated: %d new entries.",
            channel,
            inserted,
        )
        return len(pending)
