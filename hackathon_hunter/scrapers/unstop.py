"""
Unstop scraper — updated to use __NEXT_DATA__ extraction.

Strategy (Phase 1, no Playwright):
  Unstop is a Next.js SPA. Next.js embeds the entire page's server-side
  rendered data as JSON inside a <script id="__NEXT_DATA__"> tag in the
  initial HTML. This JSON is readable with plain requests — no browser
  automation needed.

  Primary URL: https://unstop.com/hackathons
  Data path:   __NEXT_DATA__ → props → pageProps → data → data (list)

  Fallback: If __NEXT_DATA__ structure changes, attempts the old REST API
  endpoint as a secondary strategy.

  Known limitation:
  - Only hackathons present in the SSR payload are captured (typically
    the first 15–30 results on the default listing page).
  - Playwright support planned for Phase 2 to handle pagination + login.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

from hackathon_hunter.config import settings
from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.scrapers.base import AbstractScraper, ScraperError

logger = logging.getLogger(__name__)

_LISTING_URL = "https://unstop.com/hackathons"
_BASE_URL = "https://unstop.com"

# Fallback REST API (may or may not work depending on Unstop's CDN rules)
_API_URL = "https://unstop.com/api/public/opportunity/search-result"
_API_PARAMS = {
    "opportunity": "hackathons",
    "start": 0,
    "per_page": 15,
    "status": "open",
    "sort": "deadline",
}


class UnstopScraper(AbstractScraper):
    """
    Scrapes hackathons from Unstop by extracting __NEXT_DATA__ JSON
    embedded in the page's initial HTML response.

    Falls back to the REST API if __NEXT_DATA__ is absent or empty.
    Returns [] with a terminal WARNING on any unrecoverable error.
    """

    platform = "unstop"

    def scrape(self) -> list[Hackathon]:
        """Return a list of hackathons found on Unstop."""
        logger.info("[unstop] Starting scrape...")
        try:
            # Strategy 1: __NEXT_DATA__ JSON extraction
            hackathons = self._scrape_next_data()
            if hackathons:
                active = self._filter_active(hackathons)
                logger.info("[unstop] Found %d active hackathon(s) via __NEXT_DATA__", len(active))
                return active

            logger.debug("[unstop] __NEXT_DATA__ empty, trying REST API fallback...")

            # Strategy 2: REST API fallback
            hackathons = self._scrape_api()
            active = self._filter_active(hackathons)
            logger.info("[unstop] Found %d active hackathon(s) via REST API", len(active))
            return active

        except ScraperError as exc:
            logger.warning("[unstop] Scraper failed: %s", exc)
            print(f"WARNING [unstop]: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("[unstop] Unexpected error during scrape", exc_info=True)
            print(f"WARNING [unstop]: Unexpected error -- {exc}")
            return []

    # ------------------------------------------------------------------
    # Strategy 1: __NEXT_DATA__ extraction
    # ------------------------------------------------------------------

    def _scrape_next_data(self) -> list[Hackathon]:
        """
        Fetch the Unstop hackathons listing page and extract the
        __NEXT_DATA__ JSON payload embedded by Next.js.
        """
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        try:
            response = requests.get(
                _LISTING_URL,
                headers={**{"User-Agent": settings.USER_AGENT}, **headers},
                timeout=settings.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise ScraperError(f"Timeout fetching {_LISTING_URL}") from exc
        except requests.HTTPError as exc:
            raise ScraperError(f"HTTP {exc.response.status_code} from {_LISTING_URL}") from exc
        except requests.RequestException as exc:
            raise ScraperError(f"Request failed: {exc}") from exc

        soup = BeautifulSoup(response.text, "lxml")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

        if not script_tag or not script_tag.string:
            logger.debug("[unstop] No __NEXT_DATA__ script tag found on page.")
            return []

        try:
            data = json.loads(script_tag.string)
        except json.JSONDecodeError as exc:
            logger.warning("[unstop] Failed to parse __NEXT_DATA__ JSON: %s", exc)
            return []

        return self._parse_next_data(data)

    def _parse_next_data(self, data: Any) -> list[Hackathon]:
        """
        Navigate the __NEXT_DATA__ structure to find hackathon entries.

        The structure varies across Next.js versions and Unstop deployments.
        We try multiple known paths and stop at the first that returns data.
        """
        hackathons: list[Hackathon] = []

        # Known paths in Unstop's __NEXT_DATA__
        candidate_paths = [
            ["props", "pageProps", "data", "data"],
            ["props", "pageProps", "opportunities", "data"],
            ["props", "pageProps", "hackathons"],
            ["props", "pageProps", "data"],
        ]

        items: list = []
        for path in candidate_paths:
            node = data
            try:
                for key in path:
                    node = node[key]
                if isinstance(node, list) and node:
                    items = node
                    logger.debug("[unstop] Found data at path: %s", " -> ".join(path))
                    break
            except (KeyError, TypeError):
                continue

        if not items:
            logger.debug("[unstop] No item list found in any known __NEXT_DATA__ path.")
            return hackathons

        for item in items:
            hackathon = self._parse_item(item)
            if hackathon:
                hackathons.append(hackathon)

        return hackathons

    # ------------------------------------------------------------------
    # Strategy 2: REST API fallback
    # ------------------------------------------------------------------

    def _scrape_api(self) -> list[Hackathon]:
        """Attempt the Unstop public REST API as a fallback."""
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": _BASE_URL,
            "Referer": _LISTING_URL,
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            response = requests.get(
                _API_URL,
                params=_API_PARAMS,
                headers={**{"User-Agent": settings.USER_AGENT}, **headers},
                timeout=settings.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise ScraperError(f"Timeout calling Unstop API") from exc
        except requests.HTTPError as exc:
            raise ScraperError(f"HTTP {exc.response.status_code} from Unstop API") from exc
        except (requests.RequestException, ValueError) as exc:
            raise ScraperError(f"Unstop API request failed: {exc}") from exc

        hackathons: list[Hackathon] = []
        try:
            items = data.get("data", {}).get("data", [])
        except AttributeError:
            logger.warning("[unstop] Unexpected REST API response shape")
            return hackathons

        for item in items:
            h = self._parse_item(item)
            if h:
                hackathons.append(h)

        return hackathons

    # ------------------------------------------------------------------
    # Shared item parser
    # ------------------------------------------------------------------

    def _parse_item(self, item: dict) -> Hackathon | None:
        """Parse a single opportunity dict into a Hackathon object."""
        try:
            title: str = (
                item.get("title")
                or item.get("name")
                or item.get("opportunity_title")
                or ""
            ).strip()

            if not title:
                return None

            # Build canonical URL
            url: str | None = None
            seo_url = item.get("seo_url")
            public_url = item.get("public_url")
            if seo_url:
                url = seo_url.strip()
            elif public_url:
                url = f"{_BASE_URL}/{public_url.lstrip('/')}"
            else:
                slug: str = (item.get("slug_name") or item.get("slug") or "").strip()
                opp_id = item.get("id")
                if slug and opp_id:
                    url = f"{_BASE_URL}/{slug}-{opp_id}"
                elif slug:
                    url = f"{_BASE_URL}/{slug}"
                elif opp_id:
                    url = f"{_BASE_URL}/o/{opp_id}"
                else:
                    return None

            # Location
            location: str | None = None
            address_data = item.get("address_with_country_logo") or {}
            if isinstance(address_data, dict):
                city = address_data.get("city")
                state = address_data.get("state")
                country_data = address_data.get("country") or {}
                country = country_data.get("name") if isinstance(country_data, dict) else None
                loc_parts = [p.strip() for p in [city, state, country] if p and str(p).strip()]
                location = ", ".join(loc_parts) if loc_parts else None

            if not location:
                location = (item.get("location") or item.get("city") or "").strip() or None

            # Deadline
            regn_reqs = item.get("regnRequirements") or {}
            deadline: str | None = None
            if isinstance(regn_reqs, dict):
                deadline = regn_reqs.get("end_regn_dt") or item.get("end_date")
            if not deadline:
                deadline = (
                    item.get("end_date")
                    or item.get("registration_deadline")
                    or item.get("deadline")
                )

            # Online/offline status
            region: str = (item.get("region") or "").lower()
            event_type: str = (item.get("type") or item.get("event_type") or "").lower()
            
            is_online: bool | None = None
            if region == "online":
                is_online = True
            elif region == "offline":
                is_online = False
            else:
                # Fallback to check keywords
                combined = f"{region} {event_type}"
                if "online" in combined or "virtual" in combined:
                    is_online = True
                elif "offline" in combined or "in-person" in combined or "in person" in combined:
                    is_online = False

            return Hackathon(
                platform=self.platform,
                name=title,
                url=url,
                location=location,
                deadline=str(deadline) if deadline else None,
                is_online=is_online,
                raw_json=json.dumps(item),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[unstop] Failed to parse item: %s", exc)
            return None

    def _filter_active(self, hackathons: list[Hackathon]) -> list[Hackathon]:
        """Filter out hackathons whose deadline has already passed."""
        now = datetime.now(timezone.utc)
        active = [h for h in hackathons if not _is_deadline_past(h.deadline, now)]
        skipped = len(hackathons) - len(active)
        if skipped:
            logger.debug("[unstop] Filtered out %d past hackathon(s) by deadline.", skipped)
        return active


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _is_deadline_past(deadline: str | None, now: datetime) -> bool:
    """
    Return True if the deadline string represents a date that has already passed.

    Unstop uses ISO 8601 timestamps (e.g. "2026-06-12T23:59:00+05:30").
    Returns False if the deadline is absent or unparseable.
    """
    if not deadline:
        return False
    try:
        dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt < now
    except (ValueError, TypeError):
        return False   # can't parse → keep it
