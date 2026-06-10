"""
Unit tests for SQLiteHackathonRepository.

Uses an in-memory SQLite database (:memory:) for all tests — no files
are created on disk. This ensures tests are fast, isolated, and idempotent.

Covers:
- initialize() creates the schema
- add() returns True for new hackathons
- add() returns False for duplicate URLs (deduplication)
- exists() returns correct boolean
- list_all() returns all records
- Multiple platforms stored correctly
- RuntimeError propagation on DB failures
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.repositories.sqlite_repository import SQLiteHackathonRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path) -> SQLiteHackathonRepository:
    """
    Return an initialized repository backed by a temporary SQLite file.
    We use tmp_path (pytest fixture) rather than :memory: to exercise the
    real file-creation path including directory auto-creation.
    """
    db_file = tmp_path / "data" / "test.db"
    r = SQLiteHackathonRepository(db_path=str(db_file))
    r.initialize()
    return r


def make_hackathon(
    name: str = "Test Hack",
    url: str = "https://example.com/hack1",
    platform: str = "testplatform",
    **kwargs,
) -> Hackathon:
    return Hackathon(platform=platform, name=name, url=url, **kwargs)


# ---------------------------------------------------------------------------
# initialize()
# ---------------------------------------------------------------------------

class TestInitialize:
    def test_initialize_creates_db_file(self, tmp_path):
        db_file = tmp_path / "data" / "hackathons.db"
        assert not db_file.exists()
        r = SQLiteHackathonRepository(db_path=str(db_file))
        r.initialize()
        assert db_file.exists()

    def test_initialize_creates_parent_directory(self, tmp_path):
        deep_path = tmp_path / "a" / "b" / "c" / "test.db"
        r = SQLiteHackathonRepository(db_path=str(deep_path))
        r.initialize()
        assert deep_path.exists()

    def test_initialize_idempotent(self, repo):
        """Calling initialize() twice should not raise."""
        repo.initialize()
        repo.initialize()

    def test_initialize_creates_hackathons_table(self, repo):
        """Verify the schema was applied by inserting and listing."""
        h = make_hackathon()
        repo.add(h)
        results = repo.list_all()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------

class TestAdd:
    def test_add_new_hackathon_returns_true(self, repo):
        h = make_hackathon()
        result = repo.add(h)
        assert result is True

    def test_add_duplicate_url_returns_false(self, repo):
        h1 = make_hackathon()
        h2 = make_hackathon(name="Different Name")  # same URL
        repo.add(h1)
        result = repo.add(h2)
        assert result is False

    def test_add_duplicate_does_not_insert(self, repo):
        h = make_hackathon()
        repo.add(h)
        repo.add(h)  # duplicate
        all_hackathons = repo.list_all()
        assert len(all_hackathons) == 1

    def test_add_different_urls_both_inserted(self, repo):
        h1 = make_hackathon(url="https://example.com/hack1")
        h2 = make_hackathon(url="https://example.com/hack2")
        assert repo.add(h1) is True
        assert repo.add(h2) is True
        assert len(repo.list_all()) == 2

    def test_add_stores_all_fields(self, repo):
        ts = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        h = make_hackathon(
            name="Full Hackathon",
            url="https://example.com/full",
            platform="devfolio",
            location="Bangalore",
            deadline="2025-11-30",
            is_online=False,
            status="NEW",
            first_seen=ts,
            raw_json='{"raw": true}',
        )
        repo.add(h)
        stored = repo.list_all()[0]
        assert stored.name == "Full Hackathon"
        assert stored.platform == "devfolio"
        assert stored.location == "Bangalore"
        assert stored.is_online is False
        assert stored.raw_json == '{"raw": true}'

    def test_add_multiple_platforms(self, repo):
        for i, platform in enumerate(["devfolio", "unstop", "openhackathons"]):
            h = make_hackathon(
                platform=platform,
                url=f"https://example.com/{platform}",
                name=f"Hack {i}",
            )
            assert repo.add(h) is True
        all_hackathons = repo.list_all()
        platforms = {h.platform for h in all_hackathons}
        assert platforms == {"devfolio", "unstop", "openhackathons"}


# ---------------------------------------------------------------------------
# exists()
# ---------------------------------------------------------------------------

class TestExists:
    def test_exists_returns_false_before_insert(self, repo):
        assert repo.exists("https://example.com/never-inserted") is False

    def test_exists_returns_true_after_insert(self, repo):
        h = make_hackathon(url="https://example.com/exists-test")
        repo.add(h)
        assert repo.exists("https://example.com/exists-test") is True

    def test_exists_case_sensitive(self, repo):
        h = make_hackathon(url="https://example.com/MyHack")
        repo.add(h)
        assert repo.exists("https://example.com/myhack") is False

    def test_exists_does_not_consume_record(self, repo):
        h = make_hackathon()
        repo.add(h)
        repo.exists(h.url)  # call exists
        assert len(repo.list_all()) == 1


# ---------------------------------------------------------------------------
# list_all()
# ---------------------------------------------------------------------------

class TestListAll:
    def test_list_all_empty_returns_empty_list(self, repo):
        assert repo.list_all() == []

    def test_list_all_returns_hackathon_instances(self, repo):
        repo.add(make_hackathon())
        results = repo.list_all()
        assert all(isinstance(h, Hackathon) for h in results)

    def test_list_all_order_newest_first(self, repo):
        from datetime import timedelta

        base_ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            h = make_hackathon(
                url=f"https://example.com/hack{i}",
                name=f"Hack {i}",
                first_seen=base_ts + timedelta(hours=i),
            )
            repo.add(h)

        results = repo.list_all()
        assert results[0].name == "Hack 2"   # newest first
        assert results[-1].name == "Hack 0"  # oldest last


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_add_raises_runtime_error_on_db_failure(self, repo, monkeypatch):
        """
        Simulate a DB write error and verify RuntimeError is raised.

        We patch sqlite3.connect at the repository module level to return a
        mock connection whose execute() raises OperationalError on INSERT.
        This avoids Python 3.12's read-only Connection.execute attribute.
        """
        import sqlite3
        from unittest.mock import MagicMock, patch

        real_connect = sqlite3.connect

        def patched_connect(path, *args, **kwargs):
            real_conn = real_connect(path, *args, **kwargs)
            mock_conn = MagicMock(wraps=real_conn)

            original_execute = real_conn.execute

            def execute_that_fails(sql, *a, **kw):
                if "INSERT" in sql.upper():
                    raise sqlite3.OperationalError("disk full")
                return original_execute(sql, *a, **kw)

            mock_conn.execute.side_effect = execute_that_fails
            # Make context manager protocol work
            mock_conn.__enter__ = lambda s: s
            mock_conn.__exit__ = MagicMock(return_value=False)
            return mock_conn

        with patch(
            "hackathon_hunter.repositories.sqlite_repository.sqlite3.connect",
            side_effect=patched_connect,
        ):
            with pytest.raises(RuntimeError, match="Failed to insert hackathon"):
                repo.add(make_hackathon())
