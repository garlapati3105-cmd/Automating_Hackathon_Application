"""hackathon_hunter.notifications package."""

from hackathon_hunter.notifications.base import BaseNotifier
from hackathon_hunter.notifications.email_notifier import EmailNotifier
from hackathon_hunter.notifications.manager import NotificationManager

__all__ = [
    "BaseNotifier",
    "EmailNotifier",
    "NotificationManager",
]
