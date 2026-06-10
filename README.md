# Hackathon Hunter 🔍

A production-ready Python 3.12 project that monitors hackathon listing sites, extracts key information, stores it in a local SQLite database, prevents duplicates, and prints newly discovered hackathons to the terminal.

---

## Features

- **3 scrapers** (Phase 1): Devfolio, Unstop, OpenHackathons
- **Duplicate prevention** via `UNIQUE` constraint on `url`
- **SQLite storage** — zero external services required
- **Pydantic models** for validated domain entities
- **Dual logging** — console (colorized) + rotating file (`logs/hackathon.log`)
- **Clean architecture** — repository pattern + service layer
- **Extensible** — add a new scraper with a single file + one line registration

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run all scrapers
```bash
python -m hackathon_hunter
```

### 3. Run a single scraper (for testing/debugging)
```bash
python -m hackathon_hunter --scraper devfolio
python -m hackathon_hunter --scraper unstop
python -m hackathon_hunter --scraper openhackathons
```

### 4. Override settings at runtime
```bash
python -m hackathon_hunter --log-level DEBUG --delay 3 --db-path /custom/path/db.sqlite
```

---

## Project Structure

```
hackathon_hunter/
├── hackathon_hunter/
│   ├── __init__.py
│   ├── __main__.py          # enables python -m hackathon_hunter
│   ├── cli.py               # argparse CLI entry-point
│   ├── main.py              # orchestration
│   ├── config/
│   │   └── settings.py      # centralized configuration
│   ├── models/
│   │   └── hackathon.py     # Pydantic domain model
│   ├── repositories/
│   │   ├── base.py          # AbstractHackathonRepository
│   │   └── sqlite_repository.py
│   ├── services/
│   │   └── scraper_service.py
│   └── scrapers/
│       ├── base.py          # AbstractScraper
│       ├── devfolio.py
│       ├── unstop.py
│       └── openhackathons.py
├── data/
│   └── hackathons.db        # auto-created
├── logs/
│   └── hackathon.log        # auto-created, rotating 5 MB × 3
├── tests/
│   ├── test_models.py
│   ├── test_repository.py
│   └── test_scraper_service.py
├── requirements.txt
└── pyproject.toml
```

---

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS hackathons (
    id         INTEGER   PRIMARY KEY AUTOINCREMENT,
    platform   TEXT      NOT NULL,
    name       TEXT      NOT NULL,
    url        TEXT      NOT NULL UNIQUE,
    location   TEXT,
    deadline   TEXT,
    is_online  INTEGER,
    status     TEXT      DEFAULT 'NEW',
    first_seen TIMESTAMP,
    raw_json   TEXT
);
```

---

## Configuration (`hackathon_hunter/config/settings.py`)

All values can be overridden via environment variables:

| Setting | Default | Env Var |
|---|---|---|
| `DATABASE_PATH` | `data/hackathons.db` | `HH_DATABASE_PATH` |
| `USER_AGENT` | `HackathonHunter/1.0` | `HH_USER_AGENT` |
| `REQUEST_TIMEOUT` | `15` | `HH_REQUEST_TIMEOUT` |
| `SCRAPER_DELAY_SECONDS` | `2` | `HH_SCRAPER_DELAY` |
| `LOG_LEVEL` | `INFO` | `HH_LOG_LEVEL` |
| `LOG_FILE` | `logs/hackathon.log` | `HH_LOG_FILE` |

---

## Adding a New Scraper (Phase 2+)

1. Create `hackathon_hunter/scrapers/mysite.py`:
```python
from hackathon_hunter.scrapers.base import AbstractScraper
from hackathon_hunter.models.hackathon import Hackathon

class MySiteScraper(AbstractScraper):
    platform = "mysite"

    def scrape(self) -> list[Hackathon]:
        # your implementation
        ...
```

2. Register it in `hackathon_hunter/main.py`:
```python
from hackathon_hunter.scrapers.mysite import MySiteScraper

scrapers = [
    DevfolioScraper(),
    UnstopScraper(),
    OpenHackathonsScraper(),
    MySiteScraper(),   # ← add this line only
]
```

**Zero changes** required elsewhere.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Notes

> **JavaScript-heavy sites**: Devfolio and Unstop are React SPAs. Phase 1 scrapers attempt public REST APIs where available and fall back to static HTML parsing. Playwright will be added in Phase 2 for full dynamic-page support.

---

## GitHub Actions Automation 🤖

Hackathon Hunter includes a pre-built workflow that runs automatically **every 30 minutes**, sends email notifications, and persists the database across runs.

### 1. Configure GitHub Repository Secrets

Go to your repository → **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret Name | Example Value | Description |
| :--- | :--- | :--- |
| `HH_EMAIL_ENABLED` | `true` | Enable email notifications |
| `HH_EMAIL_SENDER` | `you@gmail.com` | Gmail sender address |
| `HH_EMAIL_PASSWORD` | `abcd efgh ijkl mnop` | Gmail App Password (16 chars) |
| `HH_EMAIL_RECIPIENTS` | `you@gmail.com` | Comma-separated recipient list |

> **How to get a Gmail App Password:**
> Google Account → Security → 2-Step Verification → App Passwords → Select app: Mail

### 2. Push the Workflow File

The workflow is located at `.github/workflows/monitor.yml`. Commit and push it to your default branch to activate it:

```bash
git add .github/workflows/monitor.yml
git commit -m "Add GitHub Actions automation"
git push
```

### 3. Manual Trigger

Navigate to **Actions → Hackathon Hunter Monitor → Run workflow**.
Optionally enable `debug_mode` to get verbose logs for that run.

### 4. How Database Persistence Works

The SQLite database (`data/hackathons.db`) is preserved across runs using **GitHub Artifacts**:

```
Run N:   Download last successful artifact → Scrape → Upload updated artifact
Run N+1: Download Run N artifact → Scrape (deduplication works!) → Upload updated artifact
```

- **First run**: No artifact exists → starts with a clean database.
- **Missing artifact**: Download fails gracefully → starts with a clean database.
- **Corrupted database**: `PRAGMA integrity_check` detects corruption → deletes the file and starts fresh.

### 5. Workflow Features

| Feature | Details |
| :--- | :--- |
| **Schedule** | Every 30 minutes (`*/30 * * * *`) |
| **Concurrency** | Only 1 run at a time (subsequent triggers queue, never cancel) |
| **Test gate** | `pytest tests/ -v` runs first; scraper blocked on test failure |
| **Retry logic** | Scraper retried up to 3 times (10s delay between attempts) |
| **Failure logging** | Last 100 lines of `logs/hackathon.log` dumped on failure |
| **Job Summary** | Markdown table of per-platform results posted to Actions tab |
| **Artifact retention** | Database artifact kept for 30 days |

