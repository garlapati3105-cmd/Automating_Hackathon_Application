"""
Scraper service — orchestration layer.

Responsibilities:
- Accept a list of AbstractScraper instances (dependency injection).
- For each scraper, call scrape() and process the results.
- For each discovered hackathon:
  - Check if it already exists in the repository.
  - If new: insert it and print it to the terminal.
  - If duplicate: count it as skipped.
- After all scrapers finish, send ONE summary notification via
  NotificationManager (if configured) covering all newly found hackathons.
- Return a structured summary for each scraper run.

Design notes:
- This service does NOT know about SQLite — it only depends on
  AbstractHackathonRepository.
- NotificationManager is optional; omitting it (e.g. in tests) disables
  notifications without any code changes.
- Adding a new scraper requires only registering it in main.py.
  No changes to this file are needed.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.repositories.base import AbstractHackathonRepository
from hackathon_hunter.scrapers.base import AbstractScraper

if TYPE_CHECKING:
    from hackathon_hunter.notifications.manager import NotificationManager

logger = logging.getLogger(__name__)

# Terminal colour codes (ANSI)
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RESET = "\033[0m"
_BOLD = "\033[1m"
_RED = "\033[91m"


@dataclass
class ScraperResult:
    """Summary statistics for a single scraper run."""

    platform: str
    found: int = 0
    inserted: int = 0
    skipped: int = 0
    errors: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"[{self.platform}] "
            f"found={self.found} | new={self.inserted} | "
            f"dup={self.skipped} | err={self.errors}"
        )


class ScraperService:
    """
    Orchestrates multiple scrapers against a shared repository.

    Args:
        repository:           Any AbstractHackathonRepository implementation.
        scrapers:             List of AbstractScraper instances to run.
        notification_manager: Optional NotificationManager. When provided,
                              a single batch notification is sent after all
                              scrapers complete. Omit in tests to suppress
                              email/notification calls.
    """

    def __init__(
        self,
        repository: AbstractHackathonRepository,
        scrapers: list[AbstractScraper],
        notification_manager: Optional[NotificationManager] = None,
    ) -> None:
        self._repo = repository
        self._scrapers: dict[str, AbstractScraper] = {
            s.platform: s for s in scrapers
        }
        self._notification_manager = notification_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_all(self) -> list[ScraperResult]:
        """
        Run every registered scraper in order, then send one batch notification.

        Returns:
            A list of ScraperResult objects, one per scraper.
        """
        logger.info(
            "Starting run for %d scraper(s): %s",
            len(self._scrapers),
            ", ".join(self._scrapers.keys()),
        )
        results: list[ScraperResult] = []
        all_new_hackathons: list[Hackathon] = []

        for platform, scraper in self._scrapers.items():
            result, new_hackathons = self._run_scraper(scraper)
            results.append(result)
            all_new_hackathons.extend(new_hackathons)

        self._print_summary(results)

        # Send ONE batch notification covering all new hackathons from this run
        if self._notification_manager and all_new_hackathons:
            logger.info(
                "Dispatching batch notification for %d new hackathon(s).",
                len(all_new_hackathons),
            )
            self._notification_manager.notify_batch(all_new_hackathons)
        elif all_new_hackathons:
            logger.debug(
                "No notification manager configured — skipping notification "
                "for %d new hackathon(s).",
                len(all_new_hackathons),
            )

        return results

    def run_one(self, platform_name: str) -> ScraperResult:
        """
        Run a single registered scraper by platform name.

        Args:
            platform_name: The scraper's ``platform`` identifier
                           (e.g. "devfolio", "unstop").

        Returns:
            ScraperResult for the single scraper.

        Raises:
            ValueError: If no scraper is registered for ``platform_name``.
        """
        platform_name = platform_name.lower().strip()
        scraper = self._scrapers.get(platform_name)

        if scraper is None:
            valid = ", ".join(sorted(self._scrapers.keys()))
            raise ValueError(
                f"No scraper registered for '{platform_name}'. "
                f"Valid options: {valid}"
            )

        logger.info("Running single scraper: %s", platform_name)
        result, new_hackathons = self._run_scraper(scraper)
        self._print_summary([result])

        # Send batch notification for single-scraper runs too
        if self._notification_manager and new_hackathons:
            logger.info(
                "Dispatching batch notification for %d new hackathon(s).",
                len(new_hackathons),
            )
            self._notification_manager.notify_batch(new_hackathons)

        return result

    @property
    def registered_platforms(self) -> list[str]:
        """Return a sorted list of registered platform names."""
        return sorted(self._scrapers.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_scraper(self, scraper: AbstractScraper) -> tuple[ScraperResult, list[Hackathon]]:
        """
        Execute one scraper and process its results against the repository.

        Returns:
            Tuple of (ScraperResult, list of newly inserted Hackathon objects).
        """
        result = ScraperResult(platform=scraper.platform)
        new_hackathons: list[Hackathon] = []

        # scraper.scrape() never raises — it handles its own errors internally
        hackathons: list[Hackathon] = scraper.scrape()
        result.found = len(hackathons)

        for hackathon in hackathons:
            try:
                inserted = self._repo.add(hackathon)
                if inserted:
                    result.inserted += 1
                    new_hackathons.append(hackathon)
                    self._print_new_hackathon(hackathon)

                    # Insert placeholder in registration_analysis table
                    try:
                        db_path = getattr(self._repo, "_db_path", "data/hackathons.db")
                        from hackathon_hunter.repositories.registration_analysis_repository import RegistrationAnalysisRepository
                        analysis_repo = RegistrationAnalysisRepository(db_path=db_path)
                        analysis_repo.initialize()
                        analysis_repo.save_placeholder(hackathon.url, hackathon.name)
                    except Exception as exc:
                        logger.warning("Failed to save analysis placeholder: %s", exc)
                else:
                    result.skipped += 1
                    logger.debug(
                        "Duplicate skipped: [%s] %s",
                        hackathon.platform,
                        hackathon.url,
                    )
            except RuntimeError as exc:
                result.errors += 1
                logger.error(
                    "DB error for [%s] '%s': %s",
                    hackathon.platform,
                    hackathon.url,
                    exc,
                )
                print(f"[!!]  ERROR [{hackathon.platform}]: DB insert failed -- {exc}")

        logger.info("%s", result)
        return result, new_hackathons

    def _print_new_hackathon(self, hackathon: Hackathon) -> None:
        """Print a newly discovered hackathon to the terminal."""
        print(f"\n{_BOLD}{_GREEN}[+] NEW HACKATHON FOUND{_RESET}")
        print(hackathon.display())
        print()

    def _print_summary(self, results: list[ScraperResult]) -> None:
        """Print a summary table after all scrapers have run.

        Also writes a GitHub Actions Step Summary markdown table when the
        GITHUB_STEP_SUMMARY environment variable is set (i.e. running in CI).
        """
        total_new = sum(r.inserted for r in results)
        total_found = sum(r.found for r in results)
        total_errors = sum(r.errors for r in results)

        # ── Terminal output ──────────────────────────────────────
        print("\n" + "-" * 55)
        print(f"{_BOLD}  HACKATHON HUNTER -- Run Summary{_RESET}")
        print("-" * 55)
        for r in results:
            status_icon = "[OK]" if r.errors == 0 else "[!!]"
            print(
                f"  {status_icon} {r.platform:<20} "
                f"found={r.found:<4} new={r.inserted:<4} dup={r.skipped:<4}"
            )
        print("-" * 55)
        print(
            f"  {_BOLD}Total:{_RESET} "
            f"{total_found} scraped | {_GREEN}{total_new} new{_RESET}"
        )
        print("-" * 55)

        # ── GitHub Actions Step Summary ─────────────────────────
        # Written only when running inside a GitHub Actions runner.
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if summary_path:
            status_emoji = "✅" if total_errors == 0 else "⚠️"
            lines = [
                "### 🚀 Hackathon Hunter — Scraper Results",
                "",
                f"| Platform | Found | New | Duplicates | Errors | Status |",
                f"| :--- | ---: | ---: | ---: | ---: | :---: |",
            ]
            for r in results:
                icon = "✅" if r.errors == 0 else "❌"
                lines.append(
                    f"| {r.platform} | {r.found} | {r.inserted} | {r.skipped} | {r.errors} | {icon} |"
                )
            lines += [
                f"| **Total** | **{total_found}** | **{total_new}** | | **{total_errors}** | {status_emoji} |",
                "",
            ]
            try:
                with open(summary_path, "a", encoding="utf-8") as fh:
                    fh.write("\n".join(lines) + "\n")
            except OSError as exc:
                logger.debug("Could not write GitHub Step Summary: %s", exc)
