"""
Devfolio scraper.

Strategy:
  Devfolio is a React SPA. The public listing page at
  https://devfolio.co/hackathons does not render hackathon cards in the
  initial HTML response. However, Devfolio exposes a public GraphQL-style
  search endpoint that the SPA uses internally.

  We call their public search API with a JSON payload and parse the JSON
  response. No browser automation is needed for this endpoint.

  Endpoint: POST https://api.devfolio.co/api/search/hackathons
  Known limitation: Only upcoming/open hackathons are returned by default.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import requests

from hackathon_hunter.config import settings
from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.scrapers.base import AbstractScraper, ScraperError

logger = logging.getLogger(__name__)

_API_URL = "https://api.devfolio.co/api/search/hackathons"
_LISTING_URL = "https://devfolio.co/hackathons"

# Maximum hackathons to fetch per run (one page).
_PAGE_SIZE = 30


class DevfolioScraper(AbstractScraper):
    """
    Scrapes upcoming hackathons listed on Devfolio.

    Uses Devfolio's internal search API (JSON over HTTPS).
    Falls back to an empty list if the API shape changes or is unavailable.
    """

    platform = "devfolio"

    def scrape(self) -> list[Hackathon]:
        """Return a list of hackathons found on Devfolio."""
        logger.info("[devfolio] Starting scrape...")
        try:
            return self._fetch_from_api()
        except ScraperError as exc:
            logger.warning("[devfolio] Scraper failed: %s", exc)
            print(f"WARNING [devfolio]: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[devfolio] Unexpected error during scrape",
                exc_info=True,
            )
            print(f"WARNING [devfolio]: Unexpected error -- {exc}")
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_from_api(self) -> list[Hackathon]:
        """Call Devfolio's public search API and parse hackathon entries."""
        # Use today's date so the API only returns current/upcoming hackathons.
        today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = {
            "q": "",
            "filters": {
                "status": ["open"],
                "from_date": today_iso,   # exclude events whose deadline has passed
            },
            "size": _PAGE_SIZE,
            "from": 0,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": _LISTING_URL,
        }

        logger.debug("[devfolio] Calling API: %s (from_date=%s)", _API_URL, today_iso)
        try:
            response = requests.post(
                _API_URL,
                json=payload,
                headers={**{"User-Agent": settings.USER_AGENT}, **headers},
                timeout=settings.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise ScraperError(
                f"Timeout after {settings.REQUEST_TIMEOUT}s calling Devfolio API"
            ) from exc
        except requests.HTTPError as exc:
            raise ScraperError(
                f"HTTP {exc.response.status_code} from Devfolio API"
            ) from exc
        except (requests.RequestException, ValueError) as exc:
            raise ScraperError(f"Devfolio API request failed: {exc}") from exc

        hackathons = self._parse_api_response(data)

        # Secondary guard: drop anything whose deadline we can parse as past.
        now = datetime.now(timezone.utc)
        active = [h for h in hackathons if not _is_deadline_past(h.deadline, now)]
        skipped = len(hackathons) - len(active)
        if skipped:
            logger.debug(
                "[devfolio] Filtered out %d past hackathon(s) by deadline.", skipped
            )

        logger.info("[devfolio] Found %d hackathon(s)", len(active))
        return active

    def _parse_api_response(self, data: Any) -> list[Hackathon]:
        """
        Parse the JSON response from Devfolio's API.

        Expected shape (may vary):
        {
          "hits": {
            "hits": [
              {
                "_source": {
                  "name": "...",
                  "slug": "...",
                  "starts_at": "...",
                  "ends_at": "...",
                  "city": "...",
                  "is_online": true/false,
                  ...
                }
              }
            ]
          }
        }
        """
        hackathons: list[Hackathon] = []

        try:
            hits = data.get("hits", {}).get("hits", [])
        except AttributeError:
            logger.warning("[devfolio] Unexpected API response shape: %r", data)
            return hackathons

        for hit in hits:
            try:
                source: dict = hit.get("_source", {})
                name: str = source.get("name", "").strip()
                slug: str = source.get("slug", "").strip()

                if not name or not slug:
                    continue

                url = f"https://devfolio.co/{slug}"
                location: str | None = source.get("city") or source.get("venue")
                deadline: str | None = source.get("submission_deadline") or source.get("ends_at")
                is_online: bool | None = source.get("is_online")

                hackathons.append(
                    Hackathon(
                        platform=self.platform,
                        name=name,
                        url=url,
                        location=location or None,
                        deadline=deadline or None,
                        is_online=bool(is_online) if is_online is not None else None,
                        raw_json=json.dumps(source),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[devfolio] Failed to parse hit, skipping: %s", exc
                )
                continue

        return hackathons


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _is_deadline_past(deadline: str | None, now: datetime) -> bool:
    """
    Return True if the deadline string represents a date that has already passed.

    Devfolio uses ISO 8601 timestamps (e.g. "2022-03-20T11:30:00+00:00").
    Returns False (do NOT filter) if the deadline is absent or unparseable,
    so we never accidentally drop a hackathon we can't evaluate.
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
