"""
Hackathon Hunter — CLI entry point.

Usage:
    python -m hackathon_hunter                          # run all scrapers
    python -m hackathon_hunter --scraper devfolio       # single scraper
    python -m hackathon_hunter --log-level DEBUG        # verbose logging
    python -m hackathon_hunter --delay 5                # 5-second delay
    python -m hackathon_hunter --db-path /tmp/test.db   # custom DB path
"""

from __future__ import annotations

import argparse
import sys

from hackathon_hunter.config import settings
from hackathon_hunter.logging_setup import configure_logging


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hackathon_hunter",
        description="🔍 Hackathon Hunter — monitor hackathon listing sites.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m hackathon_hunter
  python -m hackathon_hunter --scraper devfolio
  python -m hackathon_hunter --scraper unstop --log-level DEBUG
  python -m hackathon_hunter --delay 5
        """,
    )

    parser.add_argument(
        "--scraper",
        metavar="NAME",
        default=None,
        help=(
            "Run only the named scraper. "
            "Valid values: devfolio | unstop | devpost | mlh. "
            "Omit to run all scrapers."
        ),
    )
    parser.add_argument(
        "--db-path",
        metavar="PATH",
        default=None,
        help=f"Path to the SQLite database file (default: {settings.DATABASE_PATH}).",
    )
    parser.add_argument(
        "--log-level",
        metavar="LEVEL",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=f"Console logging level (default: {settings.LOG_LEVEL}).",
    )
    parser.add_argument(
        "--delay",
        metavar="SECONDS",
        type=float,
        default=None,
        help=f"Seconds to wait between page requests (default: {settings.SCRAPER_DELAY_SECONDS}).",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse arguments, configure logging, and run the scraper service."""
    # Intercept profile subcommands
    if len(sys.argv) > 1 and sys.argv[1] == "profile":
        if len(sys.argv) > 2 and sys.argv[2] == "validate":
            try:
                if hasattr(sys.stdout, "reconfigure"):
                    sys.stdout.reconfigure(encoding="utf-8")
                if hasattr(sys.stderr, "reconfigure"):
                    sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass
            from hackathon_hunter.services.profile_service import ProfileService
            service = ProfileService()
            try:
                profile = service.load_profile()
                service.validate_profile(profile)
                try:
                    print("✅ Profile is valid!")
                except UnicodeEncodeError:
                    print("Profile is valid!")
                sys.exit(0)
            except Exception as exc:
                try:
                    print(f"❌ Profile validation failed:\n{exc}", file=sys.stderr)
                except UnicodeEncodeError:
                    print(f"[ERROR] Profile validation failed:\n{exc}", file=sys.stderr)
                sys.exit(1)
        else:
            print("Unknown profile subcommand. Did you mean 'validate'?", file=sys.stderr)
            sys.exit(1)

    parser = _build_parser()
    args = parser.parse_args()

    # Apply runtime overrides to settings module before any component reads them
    if args.delay is not None:
        settings.SCRAPER_DELAY_SECONDS = args.delay

    # Configure logging (before any other import that might log)
    configure_logging(log_level=args.log_level)

    # Lazy import to avoid circular imports and ensure logging is set up first
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Hackathon Hunter starting up.")

    # Import here after logging is configured
    from hackathon_hunter.main import run  # noqa: PLC0415

    try:
        run(
            db_path=args.db_path,
            scraper_name=args.scraper,
        )
    except ValueError as exc:
        # Raised by run_one() when --scraper value is unknown
        print(f"\n❌  Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚡  Interrupted by user. Exiting.", file=sys.stderr)
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        logger.critical("Fatal error: %s", exc, exc_info=True)
        print(f"\n💥  Fatal error: {exc}", file=sys.stderr)
        sys.exit(2)

    logger.info("Hackathon Hunter finished.")
