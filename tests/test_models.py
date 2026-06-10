"""
Unit tests for the Hackathon Pydantic model.

Covers:
- Required field validation
- Default value assignment
- UTC timezone enforcement on first_seen
- strip_and_require validator
- to_db_dict() serialization
- from_db_row() deserialization round-trip
- display() output format
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from hackathon_hunter.models.hackathon import Hackathon


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_hackathon(**overrides) -> Hackathon:
    """Return a minimal valid Hackathon with optional field overrides."""
    defaults = {
        "platform": "testplatform",
        "name": "Test Hackathon 2025",
        "url": "https://example.com/hackathons/test-2025",
    }
    return Hackathon(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# Construction & defaults
# ---------------------------------------------------------------------------

class TestHackathonConstruction:
    def test_minimal_valid_hackathon(self):
        h = make_hackathon()
        assert h.platform == "testplatform"
        assert h.name == "Test Hackathon 2025"
        assert h.url == "https://example.com/hackathons/test-2025"
        assert h.status == "NEW"
        assert h.location is None
        assert h.deadline is None
        assert h.is_online is None
        assert h.raw_json is None

    def test_first_seen_defaults_to_utc(self):
        h = make_hackathon()
        assert h.first_seen.tzinfo is not None
        assert h.first_seen.tzinfo == timezone.utc

    def test_full_hackathon_construction(self):
        h = make_hackathon(
            location="Bangalore, India",
            deadline="2025-12-31T23:59:59Z",
            is_online=False,
            status="NEW",
            raw_json='{"key": "value"}',
        )
        assert h.location == "Bangalore, India"
        assert h.is_online is False
        assert h.raw_json == '{"key": "value"}'


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

class TestHackathonValidators:
    def test_missing_platform_raises(self):
        with pytest.raises(ValidationError):
            Hackathon(name="Test", url="https://example.com")

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            Hackathon(platform="x", url="https://example.com")

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError):
            Hackathon(platform="x", name="Test")

    def test_empty_platform_raises(self):
        with pytest.raises(ValidationError):
            make_hackathon(platform="   ")

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            make_hackathon(name="")

    def test_empty_url_raises(self):
        with pytest.raises(ValidationError):
            make_hackathon(url="  ")

    def test_whitespace_is_stripped(self):
        h = make_hackathon(name="  My Hackathon  ", platform="  devfolio  ")
        assert h.name == "My Hackathon"
        assert h.platform == "devfolio"

    def test_naive_datetime_converted_to_utc(self):
        naive = datetime(2025, 6, 1, 12, 0, 0)
        h = make_hackathon(first_seen=naive)
        assert h.first_seen.tzinfo == timezone.utc

    def test_utc_datetime_preserved(self):
        utc_dt = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        h = make_hackathon(first_seen=utc_dt)
        assert h.first_seen == utc_dt

    def test_iso_string_first_seen(self):
        h = make_hackathon(first_seen="2025-01-15T10:30:00Z")
        assert h.first_seen.year == 2025
        assert h.first_seen.tzinfo is not None


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestHackathonSerialization:
    def test_to_db_dict_keys(self):
        h = make_hackathon()
        d = h.to_db_dict()
        expected_keys = {
            "platform", "name", "url", "location", "deadline",
            "is_online", "status", "first_seen", "raw_json"
        }
        assert set(d.keys()) == expected_keys

    def test_to_db_dict_is_online_none(self):
        h = make_hackathon(is_online=None)
        assert h.to_db_dict()["is_online"] is None

    def test_to_db_dict_is_online_true(self):
        h = make_hackathon(is_online=True)
        assert h.to_db_dict()["is_online"] == 1

    def test_to_db_dict_is_online_false(self):
        h = make_hackathon(is_online=False)
        assert h.to_db_dict()["is_online"] == 0

    def test_to_db_dict_first_seen_is_string(self):
        h = make_hackathon()
        first_seen = h.to_db_dict()["first_seen"]
        assert isinstance(first_seen, str)
        # Should be parseable as ISO 8601
        parsed = datetime.fromisoformat(first_seen)
        assert parsed.tzinfo is not None

    def test_from_db_row_round_trip(self):
        original = make_hackathon(
            location="Mumbai",
            is_online=False,
            deadline="2025-11-30",
        )
        db_dict = original.to_db_dict()
        # Simulate what SQLite returns (is_online as int)
        restored = Hackathon.from_db_row(db_dict)
        assert restored.platform == original.platform
        assert restored.name == original.name
        assert restored.url == original.url
        assert restored.location == original.location
        assert restored.is_online is False

    def test_from_db_row_with_int_is_online(self):
        row = {
            "platform": "test",
            "name": "Test Hack",
            "url": "https://example.com",
            "location": None,
            "deadline": None,
            "is_online": 1,
            "status": "NEW",
            "first_seen": "2025-01-01T00:00:00+00:00",
            "raw_json": None,
        }
        h = Hackathon.from_db_row(row)
        assert h.is_online is True


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class TestHackathonDisplay:
    def test_display_contains_name(self):
        h = make_hackathon()
        assert "Test Hackathon 2025" in h.display()

    def test_display_contains_url(self):
        h = make_hackathon()
        assert "example.com" in h.display()

    def test_display_online_tag(self):
        h = make_hackathon(is_online=True)
        assert "Online" in h.display()

    def test_display_inperson_tag(self):
        h = make_hackathon(is_online=False)
        assert "In-Person" in h.display()

    def test_display_unknown_tag(self):
        h = make_hackathon(is_online=None)
        assert "Unknown" in h.display()
