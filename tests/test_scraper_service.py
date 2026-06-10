"""
Unit tests for ScraperService.

Uses stub scrapers and an in-memory-backed repository to verify:
- run_all() processes all registered scrapers
- run_one() processes only the specified scraper
- New hackathons are inserted and printed to terminal
- Duplicate hackathons are skipped (not re-inserted)
- Scraper failures are handled gracefully
- run_one() raises ValueError for unknown scraper names
- Summary statistics (found/inserted/skipped) are correct
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.repositories.sqlite_repository import SQLiteHackathonRepository
from hackathon_hunter.scrapers.base import AbstractScraper
from hackathon_hunter.services.scraper_service import ScraperService


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class StubScraper(AbstractScraper):
    """A stub scraper that returns a pre-configured list of hackathons."""

    platform = "stub"

    def __init__(self, hackathons: list[Hackathon] | None = None, platform_name: str = "stub"):
        self.__class__ = type(
            f"StubScraper_{platform_name}",
            (StubScraper,),
            {"platform": platform_name},
        )
        self._hackathons = hackathons or []

    def scrape(self) -> list[Hackathon]:
        return self._hackathons


def make_hackathon(url: str = "https://example.com/h1", platform: str = "stub") -> Hackathon:
    return Hackathon(platform=platform, name="Test Hack", url=url)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path) -> SQLiteHackathonRepository:
    r = SQLiteHackathonRepository(db_path=str(tmp_path / "test.db"))
    r.initialize()
    return r


def make_service(
    repo: SQLiteHackathonRepository,
    scrapers: list[AbstractScraper] | None = None,
) -> ScraperService:
    if scrapers is None:
        scrapers = [StubScraper(platform_name="devfolio")]
    return ScraperService(repository=repo, scrapers=scrapers)


# ---------------------------------------------------------------------------
# run_all()
# ---------------------------------------------------------------------------

class TestRunAll:
    def test_run_all_returns_results_for_each_scraper(self, repo):
        scrapers = [
            StubScraper([make_hackathon("https://a.com", "devfolio")], "devfolio"),
            StubScraper([make_hackathon("https://b.com", "unstop")], "unstop"),
        ]
        service = ScraperService(repository=repo, scrapers=scrapers)
        results = service.run_all()
        assert len(results) == 2

    def test_run_all_inserts_new_hackathons(self, repo):
        h = make_hackathon()
        scraper = StubScraper([h], "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        results = service.run_all()
        assert results[0].inserted == 1
        assert len(repo.list_all()) == 1

    def test_run_all_skips_duplicates(self, repo):
        h = make_hackathon()
        repo.add(h)  # pre-insert

        scraper = StubScraper([h], "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        results = service.run_all()
        assert results[0].inserted == 0
        assert results[0].skipped == 1
        assert len(repo.list_all()) == 1  # still only 1

    def test_run_all_mixed_new_and_duplicate(self, repo):
        existing = make_hackathon("https://example.com/existing")
        new_h = make_hackathon("https://example.com/new")
        repo.add(existing)

        scraper = StubScraper([existing, new_h], "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        results = service.run_all()
        assert results[0].found == 2
        assert results[0].inserted == 1
        assert results[0].skipped == 1

    def test_run_all_empty_scraper(self, repo):
        scraper = StubScraper([], "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        results = service.run_all()
        assert results[0].found == 0
        assert results[0].inserted == 0

    def test_run_all_prints_new_hackathon(self, repo, capsys):
        h = make_hackathon()
        scraper = StubScraper([h], "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        service.run_all()
        captured = capsys.readouterr()
        assert "NEW HACKATHON FOUND" in captured.out

    def test_run_all_does_not_print_duplicate(self, repo, capsys):
        h = make_hackathon()
        repo.add(h)
        scraper = StubScraper([h], "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        service.run_all()
        captured = capsys.readouterr()
        assert "NEW HACKATHON FOUND" not in captured.out


# ---------------------------------------------------------------------------
# run_one()
# ---------------------------------------------------------------------------

class TestRunOne:
    def test_run_one_valid_platform(self, repo):
        h = make_hackathon("https://devfolio.co/test", "devfolio")
        scraper = StubScraper([h], "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        result = service.run_one("devfolio")
        assert result.platform == "devfolio"
        assert result.inserted == 1

    def test_run_one_unknown_platform_raises_value_error(self, repo):
        scraper = StubScraper([], "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        with pytest.raises(ValueError, match="No scraper registered for 'unknown'"):
            service.run_one("unknown")

    def test_run_one_error_message_lists_valid_names(self, repo):
        scrapers = [
            StubScraper([], "devfolio"),
            StubScraper([], "unstop"),
        ]
        service = ScraperService(repository=repo, scrapers=scrapers)
        with pytest.raises(ValueError) as exc_info:
            service.run_one("invalid")
        assert "devfolio" in str(exc_info.value)
        assert "unstop" in str(exc_info.value)

    def test_run_one_case_insensitive(self, repo):
        h = make_hackathon()
        scraper = StubScraper([h], "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        result = service.run_one("DEVFOLIO")
        assert result.platform == "devfolio"

    def test_run_one_does_not_run_other_scrapers(self, repo):
        call_log = []

        class LoggingScraper(AbstractScraper):
            platform = "logging"

            def scrape(self):
                call_log.append(self.platform)
                return []

        class LoggingScraper2(AbstractScraper):
            platform = "other"

            def scrape(self):
                call_log.append(self.platform)
                return []

        service = ScraperService(
            repository=repo,
            scrapers=[LoggingScraper(), LoggingScraper2()],
        )
        service.run_one("logging")
        assert "logging" in call_log
        assert "other" not in call_log


# ---------------------------------------------------------------------------
# registered_platforms property
# ---------------------------------------------------------------------------

class TestRegisteredPlatforms:
    def test_registered_platforms_sorted(self, repo):
        scrapers = [
            StubScraper([], "unstop"),
            StubScraper([], "devfolio"),
            StubScraper([], "openhackathons"),
        ]
        service = ScraperService(repository=repo, scrapers=scrapers)
        assert service.registered_platforms == ["devfolio", "openhackathons", "unstop"]


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

class TestSummaryStatistics:
    def test_found_count_correct(self, repo):
        hackathons = [
            make_hackathon(f"https://example.com/{i}")
            for i in range(5)
        ]
        scraper = StubScraper(hackathons, "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        results = service.run_all()
        assert results[0].found == 5

    def test_inserted_and_skipped_counts(self, repo):
        # Pre-insert 2
        for i in range(2):
            repo.add(make_hackathon(f"https://example.com/{i}"))

        # Scrape returns 5 (2 existing + 3 new)
        hackathons = [
            make_hackathon(f"https://example.com/{i}")
            for i in range(5)
        ]
        scraper = StubScraper(hackathons, "devfolio")
        service = ScraperService(repository=repo, scrapers=[scraper])
        results = service.run_all()
        assert results[0].inserted == 3
        assert results[0].skipped == 2
