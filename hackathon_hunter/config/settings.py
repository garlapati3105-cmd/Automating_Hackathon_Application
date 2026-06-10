"""
Hackathon Hunter — Configuration Layer

All settings live here. Values are read from environment variables first,
then fall back to the defaults defined below. This makes the project
12-factor compliant without adding any extra dependencies.
"""

import os
from pathlib import Path

# Load .env from the project root (two levels up from this file).
# Must happen before ANY os.getenv() call in this module.
# Silently ignored if .env does not exist (e.g. in CI environments).
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on real environment variables


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_PATH: str = os.getenv("HH_DATABASE_PATH", "data/hackathons.db")

# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------
USER_AGENT: str = os.getenv(
    "HH_USER_AGENT",
    "HackathonHunter/1.0 (monitoring bot; +https://github.com/yourname/hackathon-hunter)",
)
REQUEST_TIMEOUT: int = int(os.getenv("HH_REQUEST_TIMEOUT", "15"))  # seconds

# ---------------------------------------------------------------------------
# Scraper behaviour
# ---------------------------------------------------------------------------
SCRAPER_DELAY_SECONDS: float = float(os.getenv("HH_SCRAPER_DELAY", "2"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("HH_LOG_LEVEL", "INFO").upper()
LOG_FILE: str = os.getenv("HH_LOG_FILE", "logs/hackathon.log")
LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB per file
LOG_BACKUP_COUNT: int = 3              # keep 3 rotated files

# ---------------------------------------------------------------------------
# Email notifications (Gmail SMTP / App Password)
# Set HH_EMAIL_ENABLED=true and fill remaining vars in .env to activate.
# ---------------------------------------------------------------------------
EMAIL_ENABLED: bool = os.getenv("HH_EMAIL_ENABLED", "false").strip().lower() == "true"
EMAIL_SENDER: str = os.getenv("HH_EMAIL_SENDER", "").strip()
EMAIL_PASSWORD: str = os.getenv("HH_EMAIL_PASSWORD", "").strip()

# Comma-separated list of recipients, e.g. "a@x.com,b@x.com"
_recipients_raw: str = os.getenv("HH_EMAIL_RECIPIENTS", "")
EMAIL_RECIPIENTS: list[str] = (
    [r.strip() for r in _recipients_raw.split(",") if r.strip()]
    if _recipients_raw
    else []
)

EMAIL_SMTP_HOST: str = os.getenv("HH_EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT: int = int(os.getenv("HH_EMAIL_SMTP_PORT", "587"))
EMAIL_SUBJECT_PREFIX: str = os.getenv("HH_EMAIL_SUBJECT_PREFIX", "[Hackathon Hunter]")

# ---------------------------------------------------------------------------
# Location Filtering
# ---------------------------------------------------------------------------
LOCATION_FILTER: str = os.getenv("HH_LOCATION_FILTER", "india").strip().lower()
INCLUDE_ONLINE: bool = os.getenv("HH_INCLUDE_ONLINE", "true").strip().lower() == "true"
PRIORITY_CITY: str = os.getenv("HH_PRIORITY_CITY", "hyderabad").strip().lower()

# ---------------------------------------------------------------------------
# Playwright Browser Automation
# ---------------------------------------------------------------------------
PAGE_STABILIZATION_DELAY_MS: int = int(os.getenv("HH_PAGE_STABILIZATION_DELAY_MS", "3000"))

# ---------------------------------------------------------------------------
# Approval Workflow System (Phase 7)
# ---------------------------------------------------------------------------
APPROVAL_BASE_URL: str = os.getenv("HH_APPROVAL_BASE_URL", "").strip()

