"""
Hackathon Hunter — Logging Setup.

Configures both console (stderr) and rotating file handlers.
Call configure_logging() once at application startup.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from hackathon_hunter.config import settings


def configure_logging(
    log_level: str | None = None,
    log_file: str | None = None,
) -> None:
    """
    Configure root logger with console and rotating-file handlers.

    Args:
        log_level: Override ``settings.LOG_LEVEL`` (e.g. "DEBUG").
        log_file:  Override ``settings.LOG_FILE`` path.
    """
    level_str = (log_level or settings.LOG_LEVEL).upper()
    level = getattr(logging, level_str, logging.INFO)
    log_path = Path(log_file or settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%SZ")

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # root captures everything; handlers filter

    # ------------------------------------------------------------------
    # Console handler
    # ------------------------------------------------------------------
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)

    # ------------------------------------------------------------------
    # Rotating file handler
    # ------------------------------------------------------------------
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # always log everything to file
    file_handler.setFormatter(formatter)

    # Avoid adding duplicate handlers if called more than once
    if not root.handlers:
        root.addHandler(console)
        root.addHandler(file_handler)
    else:
        # Replace existing handlers on reconfiguration
        root.handlers.clear()
        root.addHandler(console)
        root.addHandler(file_handler)

    logging.getLogger(__name__).debug(
        "Logging configured — level=%s file=%s", level_str, log_path.resolve()
    )
