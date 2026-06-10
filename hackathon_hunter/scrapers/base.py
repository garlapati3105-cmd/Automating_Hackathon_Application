"""
Abstract base class for all hackathon scrapers.

Every platform-specific scraper must:
1. Subclass AbstractScraper.
2. Set the ``platform`` class variable to a unique lowercase identifier.
3. Implement the ``scrape()`` method to return a list of Hackathon objects.

The shared ``fetch()`` method handles HTTP requests with the configured
User-Agent, timeout, and error handling. Subclasses should call it instead
of using requests directly to ensure consistent behaviour.

Error handling contract:
- Network / HTTP errors → log WARNING (full exception) + return [].
- Parse errors on individual items → log WARNING + skip item.
- The scraper NEVER raises to the caller.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

import requests
from bs4 import BeautifulSoup

from hackathon_hunter.config import settings
from hackathon_hunter.models.hackathon import Hackathon

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Raised internally when a scraper encounters a non-recoverable error."""


class AbstractScraper(ABC):
    """
    Base class for all hackathon scrapers.

    Class Attributes:
        platform (str): Unique lowercase identifier for the source platform.
                        Must be set by each subclass.
    """

    platform: str = ""  # subclasses must override

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "platform", ""):
            raise TypeError(
                f"{cls.__name__} must define a non-empty class attribute 'platform'."
            )

    # ------------------------------------------------------------------
    # Shared HTTP helper
    # ------------------------------------------------------------------

    def fetch(
        self,
        url: str,
        *,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        as_json: bool = False,
    ) -> BeautifulSoup | dict | list:
        """
        Perform an HTTP GET request and return the parsed response.

        Args:
            url:      Target URL.
            params:   Optional query parameters.
            headers:  Extra headers to merge with defaults.
            as_json:  If True, return the JSON-decoded response body instead
                      of a BeautifulSoup object.

        Returns:
            BeautifulSoup | dict | list depending on ``as_json``.

        Raises:
            ScraperError: On timeout, HTTP error, or JSON decode failure.
        """
        default_headers = {"User-Agent": settings.USER_AGENT}
        if headers:
            default_headers.update(headers)

        logger.debug("Fetching %s (platform=%s)", url, self.platform)

        try:
            response = requests.get(
                url,
                headers=default_headers,
                params=params,
                timeout=settings.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise ScraperError(
                f"Timeout after {settings.REQUEST_TIMEOUT}s fetching {url}"
            ) from exc
        except requests.HTTPError as exc:
            raise ScraperError(
                f"HTTP {exc.response.status_code} fetching {url}"
            ) from exc
        except requests.RequestException as exc:
            raise ScraperError(f"Request failed for {url}: {exc}") from exc

        if as_json:
            try:
                return response.json()
            except ValueError as exc:
                raise ScraperError(
                    f"Invalid JSON response from {url}"
                ) from exc

        return BeautifulSoup(response.text, "lxml")

    def _sleep(self) -> None:
        """Sleep for the configured inter-request delay."""
        time.sleep(settings.SCRAPER_DELAY_SECONDS)

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    @abstractmethod
    def scrape(self) -> list[Hackathon]:
        """
        Scrape the platform and return a list of discovered hackathons.

        Implementations must:
        - Return [] on any error (log before returning).
        - Never raise exceptions to the caller.
        - Call self._sleep() between paginated requests.
        """
        ...
