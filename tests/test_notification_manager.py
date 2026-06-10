"""
Unit tests for NotificationManager.

Verifies:
- notify_batch() deduplicates per channel before dispatching
- Each notifier in the list is independently called
- mark_notified() called only on successful send
- Failed notifiers don't block other notifiers
- Empty hackathon list skips all notifiers
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.notifications.base import BaseNotifier
from hackathon_hunter.notifications.manager import NotificationManager
from hackathon_hunter.repositories.notification_log_repository import (
    NotificationLogRepository,
)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class StubNotifier(BaseNotifier):
    """A controllable test notifier."""

    def __init__(self, channel: str = "stub", return_value: bool = True):
        self._channel = channel
        self._return_value = return_value
        self.calls: list[list[Hackathon]] = []

    @property
    def channel_name(self) -> str:
        return self._channel

    def send_batch(self, hackathons: list[Hackathon]) -> bool:
        self.calls.append(hackathons)
        return self._return_value


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def log_repo(tmp_path) -> NotificationLogRepository:
    r = NotificationLogRepository(db_path=str(tmp_path / "test.db"))
    r.initialize()
    return r


def make_hackathon(url: str = "https://example.com/h1") -> Hackathon:
    return Hackathon(platform="devpost", name="Test Hack", url=url)


def make_manager(
    notifiers: list[BaseNotifier],
    log_repo: NotificationLogRepository,
) -> NotificationManager:
    return NotificationManager(notifiers=notifiers, log_repo=log_repo)


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------

class TestEmptyInputs:
    def test_empty_hackathon_list_returns_empty_dict(self, log_repo):
        notifier = StubNotifier()
        manager = make_manager([notifier], log_repo)
        result = manager.notify_batch([])
        assert result == {}

    def test_empty_hackathon_list_does_not_call_notifiers(self, log_repo):
        notifier = StubNotifier()
        manager = make_manager([notifier], log_repo)
        manager.notify_batch([])
        assert notifier.calls == []

    def test_no_notifiers_returns_empty_dict(self, log_repo):
        manager = make_manager([], log_repo)
        result = manager.notify_batch([make_hackathon()])
        assert result == {}


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_already_notified_hackathon_is_skipped(self, log_repo):
        h = make_hackathon()
        log_repo.mark_notified([h], "stub")

        notifier = StubNotifier(channel="stub")
        manager = make_manager([notifier], log_repo)
        result = manager.notify_batch([h])

        assert result["stub"] == 0
        assert notifier.calls == []  # never called

    def test_unnotified_hackathon_is_dispatched(self, log_repo):
        h = make_hackathon()
        notifier = StubNotifier(channel="stub")
        manager = make_manager([notifier], log_repo)
        result = manager.notify_batch([h])

        assert result["stub"] == 1
        assert len(notifier.calls) == 1
        assert notifier.calls[0] == [h]

    def test_mixed_notified_and_unnotified(self, log_repo):
        h_old = make_hackathon("https://a.com/old")
        h_new = make_hackathon("https://b.com/new")
        log_repo.mark_notified([h_old], "stub")

        notifier = StubNotifier(channel="stub")
        manager = make_manager([notifier], log_repo)
        result = manager.notify_batch([h_old, h_new])

        assert result["stub"] == 1
        assert len(notifier.calls) == 1
        # Only new hackathon sent
        assert notifier.calls[0] == [h_new]

    def test_channel_dedup_is_independent(self, log_repo):
        """Notified on stub1 should still be dispatched to stub2."""
        h = make_hackathon()
        log_repo.mark_notified([h], "stub1")

        notifier1 = StubNotifier(channel="stub1")
        notifier2 = StubNotifier(channel="stub2")
        manager = make_manager([notifier1, notifier2], log_repo)
        result = manager.notify_batch([h])

        assert result["stub1"] == 0  # already notified
        assert result["stub2"] == 1  # new for this channel
        assert notifier1.calls == []
        assert len(notifier2.calls) == 1


# ---------------------------------------------------------------------------
# notification_log update
# ---------------------------------------------------------------------------

class TestLogUpdate:
    def test_mark_notified_called_on_success(self, log_repo):
        h = make_hackathon()
        notifier = StubNotifier(channel="stub", return_value=True)
        manager = make_manager([notifier], log_repo)
        manager.notify_batch([h])
        # Next run should find it already notified
        assert log_repo.is_notified(h.url, "stub") is True

    def test_mark_notified_not_called_on_failure(self, log_repo):
        h = make_hackathon()
        notifier = StubNotifier(channel="stub", return_value=False)
        manager = make_manager([notifier], log_repo)
        manager.notify_batch([h])
        # Failure → should NOT be recorded → will retry next run
        assert log_repo.is_notified(h.url, "stub") is False


# ---------------------------------------------------------------------------
# Multi-notifier isolation
# ---------------------------------------------------------------------------

class TestMultiNotifier:
    def test_all_notifiers_called(self, log_repo):
        h = make_hackathon()
        n1 = StubNotifier("email")
        n2 = StubNotifier("telegram")
        manager = make_manager([n1, n2], log_repo)
        result = manager.notify_batch([h])

        assert result["email"] == 1
        assert result["telegram"] == 1
        assert len(n1.calls) == 1
        assert len(n2.calls) == 1

    def test_failing_notifier_does_not_block_others(self, log_repo):
        h = make_hackathon()
        n_fail = StubNotifier("email", return_value=False)
        n_ok = StubNotifier("telegram", return_value=True)
        manager = make_manager([n_fail, n_ok], log_repo)
        result = manager.notify_batch([h])

        assert result["email"] == 0
        assert result["telegram"] == 1
        # telegram log updated, email not
        assert log_repo.is_notified(h.url, "email") is False
        assert log_repo.is_notified(h.url, "telegram") is True

    def test_results_keyed_by_channel_name(self, log_repo):
        h = make_hackathon()
        n1 = StubNotifier("alpha")
        n2 = StubNotifier("beta")
        manager = make_manager([n1, n2], log_repo)
        result = manager.notify_batch([h])
        assert set(result.keys()) == {"alpha", "beta"}


# ---------------------------------------------------------------------------
# Location Filtering and Sorting
# ---------------------------------------------------------------------------

class TestLocationFilteringAndSorting:
    @pytest.fixture(autouse=True)
    def setup_settings(self, monkeypatch):
        # Default settings for testing filtering
        monkeypatch.setattr("hackathon_hunter.config.settings.LOCATION_FILTER", "india")
        monkeypatch.setattr("hackathon_hunter.config.settings.INCLUDE_ONLINE", True)
        monkeypatch.setattr("hackathon_hunter.config.settings.PRIORITY_CITY", "hyderabad")

    def test_filters_non_india_locations(self, log_repo):
        h_india = Hackathon(platform="devpost", name="India Hack", url="https://in.co", location="Delhi, IN")
        h_us = Hackathon(platform="devpost", name="US Hack", url="https://us.co", location="Boston, US")
        
        notifier = StubNotifier(channel="stub")
        manager = make_manager([notifier], log_repo)
        manager.notify_batch([h_india, h_us])
        
        assert len(notifier.calls) == 1
        assert notifier.calls[0] == [h_india]  # US hackathon filtered out

    def test_includes_online_when_enabled(self, log_repo):
        h_india = Hackathon(platform="devpost", name="India Hack", url="https://in.co", location="Delhi, IN")
        h_online = Hackathon(platform="devpost", name="Online Hack", url="https://online.co", location="Online", is_online=True)
        
        notifier = StubNotifier(channel="stub")
        manager = make_manager([notifier], log_repo)
        manager.notify_batch([h_india, h_online])
        
        assert len(notifier.calls) == 1
        assert len(notifier.calls[0]) == 2

    def test_excludes_online_when_disabled(self, log_repo, monkeypatch):
        monkeypatch.setattr("hackathon_hunter.config.settings.INCLUDE_ONLINE", False)
        h_india = Hackathon(platform="devpost", name="India Hack", url="https://in.co", location="Delhi, IN")
        h_online = Hackathon(platform="devpost", name="Online Hack", url="https://online.co", location="Online", is_online=True)
        
        notifier = StubNotifier(channel="stub")
        manager = make_manager([notifier], log_repo)
        manager.notify_batch([h_india, h_online])
        
        assert len(notifier.calls) == 1
        assert notifier.calls[0] == [h_india]  # Online hackathon filtered out

    def test_sorts_by_priority(self, log_repo):
        h_india = Hackathon(platform="devpost", name="India Hack", url="https://in.co", location="Delhi, IN", is_online=False)
        h_hyd = Hackathon(platform="devpost", name="Hyd Hack", url="https://hyd.co", location="Hyderabad, Telangana", is_online=False)
        h_online = Hackathon(platform="devpost", name="Online Hack", url="https://online.co", location="Online", is_online=True)
        
        notifier = StubNotifier(channel="stub")
        manager = make_manager([notifier], log_repo)
        manager.notify_batch([h_online, h_india, h_hyd])
        
        assert len(notifier.calls) == 1
        # Should be ordered: Hyderabad -> India -> Online
        assert notifier.calls[0] == [h_hyd, h_india, h_online]

    def test_no_filtering_when_disabled(self, log_repo, monkeypatch):
        monkeypatch.setattr("hackathon_hunter.config.settings.LOCATION_FILTER", "all")
        h_india = Hackathon(platform="devpost", name="India Hack", url="https://in.co", location="Delhi, IN")
        h_us = Hackathon(platform="devpost", name="US Hack", url="https://us.co", location="Boston, US")
        
        notifier = StubNotifier(channel="stub")
        manager = make_manager([notifier], log_repo)
        manager.notify_batch([h_india, h_us])
        
        assert len(notifier.calls) == 1
        assert len(notifier.calls[0]) == 2

