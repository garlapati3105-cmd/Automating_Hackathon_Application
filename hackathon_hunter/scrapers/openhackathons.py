"""
OpenHackathons scraper.

Strategy:
  OpenHackathon (openhackathon.org) renders its event listing as static
  HTML, making it a good candidate for BeautifulSoup parsing.

  Primary target: https://www.openhackathon.org/
  Fallback target: https://openhackathon.org/hackathons

  The scraper parses hackathon card elements from the HTML and extracts:
  - name         (card title / heading)
  - url          (canonical link from the card's anchor tag)
  - location     (venue text if present)
  - deadline     (date string from the card)
  - is_online    (inferred from location text or badge)

  Known limitation:
  - The site layout may change; selectors are documented inline.
  - If parsing fails completely, the scraper returns [] and logs a warning.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from bs4 import BeautifulSoup, Tag

from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.scrapers.base import AbstractScraper, ScraperError

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.openhackathon.org"
_LISTING_URL = "https://www.openhackathon.org/"

# Selector constants — update here if the site redesigns its layout
_CARD_SELECTORS = [
    "div.hackathon-card",       # most common
    "div.event-card",
    "article.hackathon",
    "div.card",
    "li.hackathon-item",
]
_TITLE_SELECTORS = ["h2", "h3", "h1", ".hackathon-title", ".card-title", ".title"]
_LINK_SELECTORS = ["a"]
_DATE_SELECTORS = [".deadline", ".date", ".end-date", "time", ".registration-end"]
_LOCATION_SELECTORS = [".location", ".venue", ".city", ".place"]


class OpenHackathonsScraper(AbstractScraper):
    """
    Scrapes hackathons from OpenHackathon.org using HTML parsing.

    Falls back to an empty list with a logged warning if the page
    structure does not match any known selector pattern.
    """

    platform = "openhackathons"

    def scrape(self) -> list[Hackathon]:
        """Return a list of hackathons found on OpenHackathon.org."""
        logger.info("[openhackathons] Starting scrape...")
        try:
            return self._fetch_and_parse()
        except ScraperError as exc:
            logger.warning("[openhackathons] Scraper failed: %s", exc)
            print(f"⚠️  WARNING [openhackathons]: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[openhackathons] Unexpected error during scrape",
                exc_info=True,
            )
            print(f"⚠️  WARNING [openhackathons]: Unexpected error — {exc}")
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_and_parse(self) -> list[Hackathon]:
        """Fetch the listing page and parse hackathon cards."""
        soup: BeautifulSoup = self.fetch(_LISTING_URL)  # type: ignore[assignment]

        cards = self._find_cards(soup)
        if not cards:
            logger.warning(
                "[openhackathons] No hackathon cards found on %s — "
                "the page layout may have changed.",
                _LISTING_URL,
            )
            # Log a sample of the page for debugging
            logger.debug(
                "[openhackathons] Page title: %s",
                soup.title.string if soup.title else "N/A",
            )
            return []

        hackathons: list[Hackathon] = []
        for card in cards:
            hackathon = self._parse_card(card)
            if hackathon:
                hackathons.append(hackathon)

        logger.info("[openhackathons] Found %d hackathon(s)", len(hackathons))
        return hackathons

    def _find_cards(self, soup: BeautifulSoup) -> list[Tag]:
        """Try multiple CSS selectors to find hackathon card elements."""
        for selector in _CARD_SELECTORS:
            cards = soup.select(selector)
            if cards:
                logger.debug(
                    "[openhackathons] Matched %d card(s) with selector '%s'",
                    len(cards),
                    selector,
                )
                return cards  # type: ignore[return-value]

        # Last-resort: look for any <a> with text that sounds like a hackathon
        # This is a heuristic; real data may vary
        anchors = soup.find_all("a", href=True)
        hackathon_links = [
            a for a in anchors
            if a.get_text(strip=True) and "hackathon" in (a.get("href", "") + a.get_text()).lower()
        ]
        if hackathon_links:
            logger.debug(
                "[openhackathons] Heuristic match: %d anchor(s) with 'hackathon'",
                len(hackathon_links),
            )
            return hackathon_links  # type: ignore[return-value]

        return []

    def _parse_card(self, card: Tag) -> Hackathon | None:
        """
        Extract hackathon fields from a single card element.

        Returns None if a required field (name or url) cannot be extracted.
        """
        try:
            name = self._extract_text(card, _TITLE_SELECTORS)
            if not name:
                # Fallback: use the card's own text (first significant line)
                name = card.get_text(separator=" ", strip=True)[:120].strip()

            url = self._extract_url(card)
            if not url:
                return None

            if not name:
                return None

            location = self._extract_text(card, _LOCATION_SELECTORS)
            deadline = self._extract_text(card, _DATE_SELECTORS)

            # Infer online/offline from location text
            is_online: bool | None = None
            if location:
                loc_lower = location.lower()
                if "online" in loc_lower or "virtual" in loc_lower or "remote" in loc_lower:
                    is_online = True
                elif any(
                    kw in loc_lower
                    for kw in ("bangalore", "delhi", "mumbai", "hyderabad", "chennai",
                               "pune", "kolkata", "india", "campus")
                ):
                    is_online = False

            raw = {
                "name": name,
                "url": url,
                "location": location,
                "deadline": deadline,
            }

            return Hackathon(
                platform=self.platform,
                name=name,
                url=url,
                location=location or None,
                deadline=deadline or None,
                is_online=is_online,
                raw_json=json.dumps(raw),
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[openhackathons] Failed to parse card, skipping: %s", exc
            )
            return None

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_text(self, tag: Tag, selectors: list[str]) -> str | None:
        """Try each selector and return the first non-empty text found."""
        for selector in selectors:
            el = tag.select_one(selector)
            if el:
                text = el.get_text(separator=" ", strip=True)
                if text:
                    return text
        return None

    def _extract_url(self, tag: Tag) -> str | None:
        """Extract and resolve the canonical URL from a card element."""
        # If the tag itself is an anchor
        if tag.name == "a":
            href = tag.get("href", "")
        else:
            a_tag = tag.find("a", href=True)
            href = a_tag["href"] if a_tag else ""

        if not href:
            return None

        href = str(href).strip()

        # Resolve relative URLs
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if href.startswith("/"):
            return f"{_BASE_URL}{href}"
        if href.startswith("#") or not href:
            return None

        return f"{_BASE_URL}/{href}"
