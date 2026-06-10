"""
Hackathon domain model.

Uses Pydantic v2 for validation, type coercion, and clean serialization.
All timestamps are UTC-aware.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Hackathon(BaseModel):
    """
    Represents a single hackathon discovered by a scraper.

    Attributes:
        platform:   Source platform identifier (e.g. "devfolio", "unstop").
        name:       Human-readable hackathon title.
        url:        Canonical URL — used as the unique deduplication key.
        location:   City / country string, or None for online-only events.
        deadline:   Registration deadline as ISO 8601 string (optional).
        is_online:  True = fully online, False = in-person, None = unknown.
        status:     Lifecycle status tag. Defaults to "NEW".
        first_seen: UTC datetime when the entry was first discovered.
        raw_json:   Optional raw JSON payload from the source (for debugging).
    """

    platform: str
    name: str
    url: str
    location: Optional[str] = None
    deadline: Optional[str] = None
    is_online: Optional[bool] = None
    status: str = "NEW"
    first_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    raw_json: Optional[str] = None

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("platform", "name", "url", mode="before")
    @classmethod
    def strip_and_require(cls, v: Any) -> str:
        """Strip whitespace and ensure required string fields are non-empty."""
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        if not v:
            raise ValueError("Field must be a non-empty string.")
        return v

    @field_validator("first_seen", mode="before")
    @classmethod
    def ensure_utc(cls, v: Any) -> datetime:
        """Accept naive datetimes and localise them to UTC."""
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        raise ValueError(f"Cannot parse first_seen: {v!r}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def to_db_dict(self) -> dict[str, Any]:
        """
        Return a flat dict suitable for an SQLite INSERT statement.
        `is_online` is converted to an integer (SQLite has no bool type).
        `first_seen` is stored as an ISO 8601 string.
        """
        return {
            "platform": self.platform,
            "name": self.name,
            "url": self.url,
            "location": self.location,
            "deadline": self.deadline,
            "is_online": int(self.is_online) if self.is_online is not None else None,
            "status": self.status,
            "first_seen": self.first_seen.isoformat(),
            "raw_json": self.raw_json,
        }

    def display(self) -> str:
        """Human-readable single-line summary for terminal output."""
        online_tag = (
            "[Online]" if self.is_online
            else "[In-Person]" if self.is_online is False
            else "[Unknown]"
        )
        deadline_str = f"  Deadline : {self.deadline}" if self.deadline else ""
        location_str = f"  Location : {self.location}" if self.location else ""
        return (
            f"[{self.platform.upper()}] {self.name}\n"
            f"  URL      : {self.url}\n"
            f"  {online_tag}{location_str}{deadline_str}"
        )

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "Hackathon":
        """Reconstruct a Hackathon from a sqlite3 Row dict."""
        data = dict(row)
        # Convert SQLite int back to bool
        if data.get("is_online") is not None:
            data["is_online"] = bool(data["is_online"])
        return cls(**data)
