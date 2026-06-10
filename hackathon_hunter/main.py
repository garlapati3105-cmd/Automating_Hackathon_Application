"""
Hackathon Hunter — main orchestration module.

This is the single place where all concrete components are wired together
(composition root). It is intentionally thin:
  - Load environment variables from .env.
  - Construct the repository.
  - Construct the scraper list.
  - Construct the notification manager (email + future channels).
  - Construct the service.
  - Delegate execution to the service.

Phase 1 Active Scrapers:
  - DevfolioScraper   (devfolio.co)       — JSON API, working
  - UnstopScraper     (unstop.com)        — __NEXT_DATA__ + API fallback
  - DevpostScraper    (devpost.com)       — JSON API, working
  - MLHScraper        (mlh.io)            — static HTML, working

Retired (kept for reference):
  - OpenHackathonsScraper — domain unreachable, replaced by Devpost + MLH

To add a new scraper in a future phase:
  1. Create hackathon_hunter/scrapers/<site>.py subclassing AbstractScraper.
  2. Import it here and add an instance to the `scrapers` list below.
  No other file changes are required.

To add a new notification channel (Telegram, Discord, etc.):
  1. Create hackathon_hunter/notifications/<channel>.py subclassing BaseNotifier.
  2. Import it here and append an instance to `notifiers` in build_notification_manager().
  No other file changes are required.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from hackathon_hunter.config import settings
from hackathon_hunter.notifications.email_notifier import EmailNotifier
from hackathon_hunter.notifications.manager import NotificationManager
from hackathon_hunter.repositories.notification_log_repository import (
    NotificationLogRepository,
)
from hackathon_hunter.repositories.sqlite_repository import SQLiteHackathonRepository
from hackathon_hunter.scrapers.devfolio import DevfolioScraper
from hackathon_hunter.scrapers.devpost import DevpostScraper
from hackathon_hunter.scrapers.mlh import MLHScraper
from hackathon_hunter.scrapers.unstop import UnstopScraper
from hackathon_hunter.services.scraper_service import ScraperResult, ScraperService

logger = logging.getLogger(__name__)

# Load .env from project root (silently ignored if file does not exist)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)


# ---------------------------------------------------------------------------
# Notification manager factory
# ---------------------------------------------------------------------------

def build_notification_manager(db_path: str) -> Optional[NotificationManager]:
    """
    Build and return a NotificationManager if email is enabled, else None.

    The NotificationLogRepository is initialised here so the
    notification_log table is created alongside the hackathons table.

    To add more channels in the future, append notifier instances to
    the `notifiers` list below.
    """
    log_repo = NotificationLogRepository(db_path=db_path)
    log_repo.initialize()

    notifiers = []

    if settings.EMAIL_ENABLED:
        if not settings.EMAIL_SENDER or not settings.EMAIL_PASSWORD:
            logger.warning(
                "HH_EMAIL_ENABLED=true but HH_EMAIL_SENDER or HH_EMAIL_PASSWORD "
                "is not set — email notifications disabled."
            )
        elif not settings.EMAIL_RECIPIENTS:
            logger.warning(
                "HH_EMAIL_ENABLED=true but HH_EMAIL_RECIPIENTS is empty "
                "— email notifications disabled."
            )
        elif not settings.APPROVAL_BASE_URL:
            logger.error("HH_APPROVAL_BASE_URL is not set while email is enabled.")
            raise RuntimeError(
                "Configuration error: HH_APPROVAL_BASE_URL must be supplied through environment variables when HH_EMAIL_ENABLED=true."
            )
        else:
            notifiers.append(
                EmailNotifier(
                    sender=settings.EMAIL_SENDER,
                    password=settings.EMAIL_PASSWORD,
                    recipients=settings.EMAIL_RECIPIENTS,
                    smtp_host=settings.EMAIL_SMTP_HOST,
                    smtp_port=settings.EMAIL_SMTP_PORT,
                    subject_prefix=settings.EMAIL_SUBJECT_PREFIX,
                    db_path=db_path,
                )
            )
            logger.info(
                "EmailNotifier ready — sender=%s recipients=%s",
                settings.EMAIL_SENDER,
                settings.EMAIL_RECIPIENTS,
            )
    else:
        logger.info("Email notifications disabled (HH_EMAIL_ENABLED=false).")

    # Future channels:
    # if settings.TELEGRAM_ENABLED:
    #     notifiers.append(TelegramNotifier(...))

    if not notifiers:
        return None

    return NotificationManager(notifiers=notifiers, log_repo=log_repo)


# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------

def build_service(db_path: Optional[str] = None) -> ScraperService:
    """
    Wire up all components and return a ready-to-use ScraperService.

    Args:
        db_path: Optional override for the database path.
                 Defaults to settings.DATABASE_PATH.

    Returns:
        Configured ScraperService instance.
    """
    resolved_db_path = db_path or settings.DATABASE_PATH

    # ------------------------------------------------------------------
    # Repository
    # ------------------------------------------------------------------
    repo = SQLiteHackathonRepository(db_path=resolved_db_path)
    repo.initialize()

    from hackathon_hunter.repositories.registration_analysis_repository import RegistrationAnalysisRepository
    analysis_repo = RegistrationAnalysisRepository(db_path=resolved_db_path)
    analysis_repo.initialize()

    # ------------------------------------------------------------------
    # Scrapers — Phase 1 (active)
    # To add a Phase 2 scraper, append its instance here.
    # ------------------------------------------------------------------
    scrapers = [
        DevfolioScraper(),       # devfolio.co   — JSON API
        UnstopScraper(),         # unstop.com     — __NEXT_DATA__ + API fallback
        DevpostScraper(),        # devpost.com    — JSON API
        MLHScraper(),            # mlh.io         — static HTML
        # Hack2SkillScraper(),   ← Phase 2: uncomment when ready
    ]

    # ------------------------------------------------------------------
    # Notification manager (optional — None when email disabled)
    # ------------------------------------------------------------------
    notification_manager = build_notification_manager(db_path=resolved_db_path)

    return ScraperService(
        repository=repo,
        scrapers=scrapers,
        notification_manager=notification_manager,
    )


# ---------------------------------------------------------------------------
# Run entrypoint
# ---------------------------------------------------------------------------

def run(
    db_path: Optional[str] = None,
    scraper_name: Optional[str] = None,
) -> list[ScraperResult]:
    """
    Build the service and execute scraping.

    Args:
        db_path:      Optional override for the database file path.
        scraper_name: If provided, run only this named scraper.
                      If None, run all scrapers.

    Returns:
        List of ScraperResult objects.
    """
    service = build_service(db_path=db_path)

    if scraper_name:
        result = service.run_one(scraper_name)
        return [result]
    else:
        return service.run_all()

