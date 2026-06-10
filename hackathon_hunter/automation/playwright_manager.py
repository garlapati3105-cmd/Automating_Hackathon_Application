from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from hackathon_hunter.config import settings

logger = logging.getLogger(__name__)


class PlaywrightManager:
    """
    Manages Playwright sync browser instances, contexts, page navigation, 
    and cleanup.
    """

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> PlaywrightManager:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def start(self) -> None:
        """Initialize Playwright and launch the browser."""
        logger.debug("Starting Playwright...")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        self._page = self._context.new_page()

    def open_url(self, url: str) -> Page:
        """
        Navigate to a URL using the stabilization loading strategy:
        1. Wait for 'domcontentloaded'.
        2. Wait for PAGE_STABILIZATION_DELAY_MS.
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() or use context manager.")

        logger.info("Opening page: %s", url)
        self._page.goto(url, wait_until="domcontentloaded")

        delay_ms = settings.PAGE_STABILIZATION_DELAY_MS
        logger.debug("Waiting %d ms for page stabilization...", delay_ms)
        self._page.wait_for_timeout(delay_ms)
        return self._page

    def take_screenshot(self, output_path: str | Path = "screenshots/filled_form.png") -> None:
        """Capture page screenshot and save to disk."""
        if not self._page:
            raise RuntimeError("Browser not started. Cannot take screenshot.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Saving screenshot to %s", path)
        self._page.screenshot(path=str(path), full_page=True)

    def close(self) -> None:
        """Safely close page, context, browser, and stop Playwright."""
        logger.debug("Closing Playwright resources...")
        try:
            if self._page:
                self._page.close()
        except Exception:
            pass
        finally:
            self._page = None

        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        finally:
            self._context = None

        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        finally:
            self._browser = None

        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._playwright = None
