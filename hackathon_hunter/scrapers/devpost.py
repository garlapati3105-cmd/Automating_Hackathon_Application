"""
Devpost scraper.

Strategy:
  Devpost exposes an internal XHR/fetch API endpoint at:
    https://devpost.com/api/hackathons.json

  This endpoint is used by the Devpost website itself to load hackathon
  listings. It returns paginated JSON without requiring authentication
  or JavaScript execution.

  Key query parameters:
    challenge_type[]  = hackathon
    status[]          = upcoming | open
    page              = 1, 2, ...  (1-indexed)
    per_page          = 24         (Devpost default)
    order_by          = deadline   (soonest first)

  Response shape:
  {
    "hackathons": [ { "id", "title", "url", "displayed_location", ... } ],
    "meta": { "total_count", "per_page", "current_page", "total_pages" }
  }

  Known limitation:
  - Only open/upcoming hackathons are fetched (by design).
  - Very old or closed hackathons are excluded.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from hackathon_hunter.config import settings
from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.scrapers.base import AbstractScraper, ScraperError

logger = logging.getLogger(__name__)

_API_URL = "https://devpost.com/api/hackathons.json"
_LISTING_URL = "https://devpost.com/hackathons"
_MAX_PAGES = 3       # fetch up to 3 pages (~72 hackathons)
_PER_PAGE = 24


class DevpostScraper(AbstractScraper):
    """
    Scrapes open and upcoming hackathons listed on Devpost.

    Uses Devpost's internal JSON API. Paginates up to MAX_PAGES.
    Respects SCRAPER_DELAY_SECONDS between page requests.
    """

    platform = "devpost"

    def scrape(self) -> list[Hackathon]:
        """Return a list of hackathons found on Devpost."""
        logger.info("[devpost] Starting scrape...")
        try:
            return self._fetch_paginated()
        except ScraperError as exc:
            logger.warning("[devpost] Scraper failed: %s", exc)
            print(f"WARNING [devpost]: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("[devpost] Unexpected error during scrape", exc_info=True)
            print(f"WARNING [devpost]: Unexpected error -- {exc}")
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_paginated(self) -> list[Hackathon]:
        """Paginate through Devpost API and collect all hackathons."""
        all_hackathons: list[Hackathon] = []

        for page in range(1, _MAX_PAGES + 1):
            if page > 1:
                self._sleep()

            items, total_pages = self._fetch_page(page)
            if not items:
                logger.debug("[devpost] No items on page %d; stopping.", page)
                break

            all_hackathons.extend(items)
            logger.debug(
                "[devpost] Page %d/%d: +%d hackathon(s) (total: %d)",
                page, total_pages, len(items), len(all_hackathons),
            )

            if page >= total_pages:
                break

        logger.info("[devpost] Found %d hackathon(s) total", len(all_hackathons))
        return all_hackathons

    def _fetch_page(self, page: int) -> tuple[list[Hackathon], int]:
        """
        Fetch one page of results from the Devpost API.

        Returns:
            (list of Hackathon objects, total_pages int)
        """
        params = {
            "challenge_type[]": "hackathon",
            "status[]": ["upcoming", "open"],
            "page": page,
            "per_page": _PER_PAGE,
            "order_by": "deadline",
        }
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": _LISTING_URL,
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            response = requests.get(
                _API_URL,
                params=params,
                headers={**{"User-Agent": settings.USER_AGENT}, **headers},
                timeout=settings.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise ScraperError(
                f"Timeout after {settings.REQUEST_TIMEOUT}s fetching Devpost page {page}"
            ) from exc
        except requests.HTTPError as exc:
            raise ScraperError(
                f"HTTP {exc.response.status_code} from Devpost API (page={page})"
            ) from exc
        except (requests.RequestException, ValueError) as exc:
            raise ScraperError(f"Devpost API request failed (page={page}): {exc}") from exc

        hackathons = self._parse_response(data)
        meta = data.get("meta", {})
        total_pages = meta.get("total_pages", 1)

        return hackathons, int(total_pages)

    def _parse_response(self, data: Any) -> list[Hackathon]:
        """
        Parse one page of the Devpost API JSON response.

        Expected shape:
        {
          "hackathons": [
            {
              "id": 12345,
              "title": "...",
              "url": "https://hackathon-name.devpost.com",
              "displayed_location": {
                "location": "Online"
              },
              "submission_period_dates": "...",
              "open_state": "open",
              "prize_amount": "$10,000",
              ...
            }
          ],
          "meta": { "total_count": 150, "total_pages": 7, ... }
        }
        """
        hackathons: list[Hackathon] = []

        try:
            items = data.get("hackathons", [])
        except AttributeError:
            logger.warning("[devpost] Unexpected API response shape: %r", type(data))
            return hackathons

        for item in items:
            try:
                title: str = (item.get("title") or "").strip()
                url: str = (item.get("url") or "").strip()

                if not title or not url:
                    continue

                # Location is nested
                location_obj = item.get("displayed_location") or {}
                location: str | None = (
                    location_obj.get("location") or location_obj.get("country")
                    if isinstance(location_obj, dict)
                    else None
                )
                if location:
                    location = location.strip() or None

                # Deadline / submission period
                deadline: str | None = (
                    item.get("submission_period_end_date")
                    or item.get("deadline")
                    or item.get("submission_period_dates")
                )

                # Online/offline
                is_online: bool | None = None
                if location:
                    loc_lower = location.lower()
                    if "online" in loc_lower or "virtual" in loc_lower or "worldwide" in loc_lower:
                        is_online = True
                    elif loc_lower and "online" not in loc_lower:
                        is_online = False

                hackathons.append(
                    Hackathon(
                        platform=self.platform,
                        name=title,
                        url=url,
                        location=location,
                        deadline=str(deadline) if deadline else None,
                        is_online=is_online,
                        raw_json=json.dumps(item),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[devpost] Failed to parse item, skipping: %s", exc)
                continue

        return hackathons
