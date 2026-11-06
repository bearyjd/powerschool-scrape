"""ps — PowerSchool parent portal scraper. JSON on stdout only; logs on stderr."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from .browser import LoginError, PlaywrightScraper
from .config import ConfigError, load_credentials
from .summary import build_summary

log = logging.getLogger("ps")


def today() -> date:
    return date.today()


def make_scraper():
    return PlaywrightScraper(load_credentials())


def output(data: dict) -> None:
    sys.stdout.write(json.dumps(data, indent=2) + "\n")


def _fail(message: str) -> int:
    output({"error": message, "warnings": []})
    return 1


def cmd_summary(args) -> int:
    try:
        scraper = make_scraper()
        with scraper as s:
            result = build_summary(s, today(), args.days, args.child)
    except (ConfigError, LoginError) as e:
        return _fail(str(e))
    except Exception as e:
        log.error("scrape failed: %s", type(e).__name__)
        return _fail(f"scrape failed: {type(e).__name__}")
    output(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="powerschool", description="PowerSchool parent portal scraper")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("summary", help="missing / late / upcoming work per child")
    s.add_argument("--json", action="store_true", help="JSON output (always on)")
    s.add_argument("--days", type=int, default=14, help="upcoming window in days (default 14)")
    s.add_argument("--child", help="case-insensitive name substring filter")
    s.set_defaults(func=cmd_summary)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
