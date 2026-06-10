"""hackathon_hunter.scrapers package."""

from hackathon_hunter.scrapers.base import AbstractScraper, ScraperError
from hackathon_hunter.scrapers.devfolio import DevfolioScraper
from hackathon_hunter.scrapers.devpost import DevpostScraper
from hackathon_hunter.scrapers.mlh import MLHScraper
from hackathon_hunter.scrapers.openhackathons import OpenHackathonsScraper  # kept for reference
from hackathon_hunter.scrapers.unstop import UnstopScraper

__all__ = [
    "AbstractScraper",
    "ScraperError",
    "DevfolioScraper",
    "UnstopScraper",
    "DevpostScraper",
    "MLHScraper",
    "OpenHackathonsScraper",
]
