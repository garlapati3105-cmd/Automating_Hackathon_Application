"""
Unit tests for NotificationLogRepository.

Uses an in-memory SQLite database (via tmp_path) — no real file I/O.
Covers: initialize, is_notified, filter_unnotified, mark_notified,
channel isolation, and duplicate-safe re-marking.
"""

from __future__ import annotations

import pytest

from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.repositories.notification_log_repository import (
    NotificationLogRepository,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path) -> NotificationLogRepository:
    r = NotificationLogRepository(db_path=str(tmp_path / "test.db"))
    r.initialize()
    return r


def make_hackathon(url: str = "https://example.com/h1", platform: str = "devpost") -> Hackathon:
    return Hackathon(platform=platform, name="Test Hack", url=url)


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------

class TestInitialize:
    def test_initialize_is_idempotent(self, tmp_path):
        """Calling initialize() twice should not raise."""
        r = NotificationLogRepository(db_path=str(tmp_path / "test.db"))
        r.initialize()
        r.initialize()  # should not raise

    def test_initialize_creates_parent_directory(self, tmp_path):
        nested = tmp_path / "sub" / "dir" / "test.db"
        r = NotificationLogRepository(db_path=str(nested))
        r.initialize()
        assert nested.exists()


# ---------------------------------------------------------------------------
# is_notified
# ---------------------------------------------------------------------------

class TestIsNotified:
    def test_returns_false_before_any_notification(self, repo):
        h = make_hackathon()
        assert repo.is_notified(h.url, "email") is False

    def test_returns_true_after_mark_notified(self, repo):
        h = make_hackathon()
        repo.mark_notified([h], "email")
        assert repo.is_notified(h.url, "email") is True

    def test_channel_isolation(self, repo):
        """Notified on 'email' does NOT count as notified on 'telegram'."""
        h = make_hackathon()
        repo.mark_notified([h], "email")
        assert repo.is_notified(h.url, "telegram") is False

    def test_different_urls_independently_tracked(self, repo):
        h1 = make_hackathon("https://a.com/h1")
        h2 = make_hackathon("https://b.com/h2")
        repo.mark_notified([h1], "email")
        assert repo.is_notified(h1.url, "email") is True
        assert repo.is_notified(h2.url, "email") is False


# ---------------------------------------------------------------------------
# filter_unnotified
# ---------------------------------------------------------------------------

class TestFilterUnnotified:
    def test_all_returned_when_none_notified(self, repo):
        hackathons = [make_hackathon(f"https://example.com/{i}") for i in range(3)]
        result = repo.filter_unnotified(hackathons, "email")
        assert result == hackathons

    def test_empty_input_returns_empty(self, repo):
        result = repo.filter_unnotified([], "email")
        assert result == []

    def test_already_notified_filtered_out(self, repo):
        h1 = make_hackathon("https://a.com/h1")
        h2 = make_hackathon("https://b.com/h2")
        repo.mark_notified([h1], "email")
        result = repo.filter_unnotified([h1, h2], "email")
        assert len(result) == 1
        assert result[0].url == h2.url

    def test_all_filtered_if_all_notified(self, repo):
        hackathons = [make_hackathon(f"https://example.com/{i}") for i in range(3)]
        repo.mark_notified(hackathons, "email")
        result = repo.filter_unnotified(hackathons, "email")
        assert result == []

    def test_channel_isolation_in_filter(self, repo):
        """Notified on 'email' should still appear in 'telegram' unnotified list."""
        h = make_hackathon()
        repo.mark_notified([h], "email")
        result = repo.filter_unnotified([h], "telegram")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# mark_notified
# ---------------------------------------------------------------------------

class TestMarkNotified:
    def test_mark_notified_returns_insert_count(self, repo):
        hackathons = [make_hackathon(f"https://example.com/{i}") for i in range(3)]
        inserted = repo.mark_notified(hackathons, "email")
        assert inserted == 3

    def test_mark_notified_empty_list_returns_zero(self, repo):
        inserted = repo.mark_notified([], "email")
        assert inserted == 0

    def test_remark_already_notified_is_safe(self, repo):
        """INSERT OR IGNORE — re-marking should not raise and returns 0."""
        h = make_hackathon()
        repo.mark_notified([h], "email")
        inserted = repo.mark_notified([h], "email")
        assert inserted == 0

    def test_mark_notified_persists_across_instances(self, tmp_path):
        """Data written by one instance is visible to another on the same DB."""
        db_path = str(tmp_path / "shared.db")
        r1 = NotificationLogRepository(db_path=db_path)
        r1.initialize()
        h = make_hackathon()
        r1.mark_notified([h], "email")

        r2 = NotificationLogRepository(db_path=db_path)
        r2.initialize()
        assert r2.is_notified(h.url, "email") is True

    def test_multiple_channels_independent_rows(self, repo):
        h = make_hackathon()
        repo.mark_notified([h], "email")
        repo.mark_notified([h], "telegram")
        assert repo.is_notified(h.url, "email") is True
        assert repo.is_notified(h.url, "telegram") is True
