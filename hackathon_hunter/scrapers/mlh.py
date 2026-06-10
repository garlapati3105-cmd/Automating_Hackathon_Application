"""
MLH (Major League Hacking) scraper.

Strategy:
  MLH publishes its official season event schedule at:
    https://mlh.io/seasons/2025/events

  The page renders static HTML. Each hackathon is an <a> tag wrapping a
  div.rounded-card element. The anchor href is the external hackathon URL
  (with MLH UTM tracking). The card contains event name, date, and location.

  Verified HTML structure (inspected 2026-06):
    <a href="https://hackathon-site.com?utm_source=mlh&...">
      <div class="rounded-card ...">
        ...
        <p>City, Country</p>
        <p>Event Name</p>
        <p>DATE RANGE</p>
        <p>City, Country, CC</p>
        <p>In-Person</p>
        ...
      </div>
    </a>

  Season URL strategy:
  - Tries the current year (2026) first, then falls back to 2025.

  Known limitation:
  - Only events listed on the current MLH season page are captured.
  - Card text layout changes could break the parser.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from bs4 import BeautifulSoup, Tag

from hackathon_hunter.config import settings
from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.scrapers.base import AbstractScraper, ScraperError

logger = logging.getLogger(__name__)

_BASE_URL = "https://mlh.io"
_SEASON_URLS = [
    "https://mlh.io/seasons/2025/events",   # confirmed working, try first
    "https://mlh.io/seasons/2026/events",   # may redirect to www.mlh.com
]

_ONLINE_KEYWORDS = {"digital", "online", "virtual", "remote", "worldwide"}
_NOISE_LINKS = {"/", "/signin", "#main-content"}


class MLHScraper(AbstractScraper):
    """
    Scrapes hackathon events from the official MLH season events page.

    Tries the 2026 season first, falls back to 2025.
    Returns [] with a terminal WARNING on any unrecoverable error.
    """

    platform = "mlh"

    def scrape(self) -> list[Hackathon]:
        """Return a list of hackathons found on MLH."""
        logger.info("[mlh] Starting scrape...")
        try:
            return self._fetch_and_parse()
        except ScraperError as exc:
            logger.warning("[mlh] Scraper failed: %s", exc)
            print(f"WARNING [mlh]: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("[mlh] Unexpected error during scrape", exc_info=True)
            print(f"WARNING [mlh]: Unexpected error -- {exc}")
            return []

    # ------------------------------------------------------------------
    # Fetch + parse
    # ------------------------------------------------------------------

    def _fetch_and_parse(self) -> list[Hackathon]:
        """Try each season URL in order; parse the first that has cards."""
        for url in _SEASON_URLS:
            logger.debug("[mlh] Trying: %s", url)
            try:
                soup: BeautifulSoup = self.fetch(url)  # type: ignore[assignment]
            except ScraperError as exc:
                logger.debug("[mlh] Failed to fetch %s: %s", url, exc)
                continue

            hackathons = self._parse_page(soup)
            if hackathons:
                # Filter out events whose end date has already passed.
                now = datetime.now(timezone.utc)
                active = [h for h in hackathons if not _mlh_date_is_past(h.deadline, now)]
                skipped = len(hackathons) - len(active)
                if skipped:
                    logger.debug(
                        "[mlh] Filtered out %d past event(s) by date.", skipped
                    )
                logger.info(
                    "[mlh] Found %d hackathon(s) at %s", len(active), url
                )
                return active
            logger.debug("[mlh] No hackathons parsed from %s, trying next.", url)

        logger.warning("[mlh] No hackathons found on any MLH season page.")
        return []

    def _parse_page(self, soup: BeautifulSoup) -> list[Hackathon]:
        """
        Parse hackathons from the MLH events page.

        Each event is an <a href="external-url"> wrapping a div.rounded-card.
        We extract:
          - URL  → from href (stripped of UTM params for a clean canonical URL)
          - Name → from the second <p> inside the card (after location city)
          - Date → from the third <p> inside the card
          - Location / online → from card text
        """
        hackathons: list[Hackathon] = []
        seen_urls: set[str] = set()

        # Every MLH event is an anchor wrapping a .rounded-card div
        event_anchors = soup.find_all("a", href=True)
        for anchor in event_anchors:
            card = anchor.find(class_="rounded-card")
            if not card:
                continue

            hackathon = self._parse_event_anchor(anchor, card)
            if hackathon and hackathon.url not in seen_urls:
                seen_urls.add(hackathon.url)
                hackathons.append(hackathon)

        return hackathons

    def _parse_event_anchor(self, anchor: Tag, card: Tag) -> Optional[Hackathon]:
        """Extract a Hackathon from a single event anchor + card pair."""
        try:
            raw_href: str = anchor.get("href", "").strip()

            # Skip navigation / social links
            if not raw_href or raw_href in _NOISE_LINKS:
                return None
            if raw_href.startswith("/") and "events" not in raw_href:
                return None

            # Strip UTM tracking params for a clean canonical URL
            url = self._clean_url(raw_href)

            # MLH card text format (pipe-separated after split):
            # "Event Name | DATE RANGE | City, Country, CC | In-Person/Digital"
            # We use pipe-separator so whitespace-only segments are easy to filter.
            raw_text = card.get_text(separator="|", strip=True)
            segments = [s.strip() for s in raw_text.split("|") if s.strip()]

            if not segments:
                return None

            name, date_str, location, is_online = self._parse_segments(segments, card)

            if not name:
                return None

            raw = {
                "href": raw_href,
                "url": url,
                "segments": segments,
            }

            return Hackathon(
                platform=self.platform,
                name=name,
                url=url,
                location=location,
                deadline=date_str,
                is_online=is_online,
                raw_json=json.dumps(raw),
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning("[mlh] Failed to parse event anchor: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Field extraction helpers
    # ------------------------------------------------------------------

    def _parse_segments(
        self, segments: list[str], card: Tag
    ) -> tuple[str | None, str | None, str | None, bool | None]:
        """
        Parse the pipe-split card text segments into (name, date, location, is_online).

        MLH card text layout (from get_text with "|" separator):
          [0]  Event Name          (longest segment, from <h4>)
          [1]  DATE RANGE          (e.g. "JUN 27 - 29")
          [2]  City, Country, CC   (e.g. "Toronto, Canada, CA")
          [3]  In-Person | Digital
        """
        date_pattern = re.compile(
            r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2}",
            re.IGNORECASE,
        )
        mode_keywords = {"digital", "online", "virtual", "hybrid", "remote", "in-person", "in person"}

        name: str | None = None
        date_str: str | None = None
        location: str | None = None
        is_online: bool | None = None

        # Try to get name from h4 tag first (most reliable)
        h4 = card.find("h4")
        if h4:
            name = h4.get_text(strip=True)[:150]

        for seg in segments:
            seg_lower = seg.lower().strip()

            # Date range
            if date_pattern.search(seg):
                date_str = seg
                continue

            # Mode
            if seg_lower in mode_keywords:
                if "digital" in seg_lower or "online" in seg_lower or "virtual" in seg_lower:
                    is_online = True
                elif "in-person" in seg_lower or "in person" in seg_lower:
                    is_online = False
                continue

            # Location: has comma + country code pattern, short length
            if "," in seg and len(seg) < 70 and not date_pattern.search(seg):
                location = seg
                continue

            # Name fallback: if no h4 found, use first long enough segment
            if name is None and len(seg) >= 4:
                name = seg[:150]

        # Check for "worldwide/everywhere" in all segments → online
        full_text = "|".join(segments).lower()
        if "worldwide" in full_text or "everywhere" in full_text:
            is_online = True

        return name, date_str, location, is_online

    def _clean_url(self, url: str) -> str:
        """Strip UTM tracking parameters from an MLH event URL."""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query, keep_blank_values=True)
            # Remove UTM and MLH tracking params
            clean_params = {
                k: v for k, v in params.items()
                if not k.startswith("utm_")
            }
            clean_query = urlencode(clean_params, doseq=True)
            cleaned = urlunparse(parsed._replace(query=clean_query))
            return cleaned
        except Exception:  # noqa: BLE001
            return url


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

_MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_MLH_DATE_RE = re.compile(
    r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})\s*-\s*(\d{1,2})",
    re.IGNORECASE,
)


def _mlh_date_is_past(deadline: str | None, now: datetime) -> bool:
    """
    Return True if the MLH event's end date has already passed.

    MLH dates look like "JUN 27 - 29" or "APR 25 - 27" — no year included.
    We infer the year: if the month is before the current month, assume next
    calendar year; otherwise assume the current year. This handles season
    pages that include both past (for context) and upcoming events.

    Returns False (keep) if the deadline is absent or unparseable.
    """
    if not deadline:
        return False
    m = _MLH_DATE_RE.search(deadline.upper())
    if not m:
        return False
    try:
        month = _MONTH_MAP[m.group(1).upper()]
        end_day = int(m.group(3))
        year = now.year
        # If this month already passed this year, it belongs to the next season
        if month < now.month or (month == now.month and end_day < now.day):
            # Past event in current year — it's over
            return True
        event_end = datetime(year, month, end_day, 23, 59, 59, tzinfo=timezone.utc)
        return event_end < now
    except (KeyError, ValueError):
        return False  # can't parse → keep it
