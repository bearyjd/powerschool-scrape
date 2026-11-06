"""Playwright layer (lazy import). Tested only via mocks / live runs."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from .config import Credentials
from .parse import parse_class_links, parse_course_name, parse_students

log = logging.getLogger("ps")

LOOKUP = "/ws/xte/assignment/lookup"
NAV_TIMEOUT_MS = 45_000


class LoginError(Exception):
    """Login failed. Never includes credentials."""


class PlaywrightScraper:
    def __init__(self, creds: Credentials):
        self._creds = creds
        self._pw = self._browser = self._page = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise LoginError("playwright is not installed (pip install 'powerschool-scrape[browser]')") from None
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            self._page = self._browser.new_page()
            self._page.set_default_timeout(NAV_TIMEOUT_MS)
            self._login()
        except LoginError:
            self.__exit__()
            raise
        except Exception as e:  # playwright errors: report class only
            self.__exit__()
            raise LoginError(f"login failed: {type(e).__name__}") from None
        return self

    def __exit__(self, *exc):
        for closer in (self._browser, self._pw):
            try:
                if closer is not None:
                    getattr(closer, "close", None) and closer.close()
                    getattr(closer, "stop", None) and closer.stop()
            except Exception:  # best-effort teardown
                log.debug("teardown error ignored")
        self._browser = self._pw = self._page = None
        return False

    def _check_host(self, what: str) -> None:
        parts = urlparse(self._page.url)
        if parts.scheme != "https" or (parts.hostname or "").lower() != self._creds.host.lower():
            raise LoginError(f"login aborted: {what} is not on the configured https host")

    def _login(self) -> None:
        p, base = self._page, self._creds.base_url
        p.goto(f"{base}/public/")
        self._check_host("login page")
        p.fill("#fieldAccount", self._creds.username)
        p.fill("#fieldPassword", self._creds.password)
        p.click("#btn-enter-sign-in")
        p.wait_for_load_state("networkidle")
        self._check_host("post-login page")
        if "/guardian/" not in p.url:
            raise LoginError("login failed: did not reach guardian home (bad credentials?)")
        log.info("login ok")

    def _home(self) -> None:
        self._page.goto(f"{self._creds.base_url}/guardian/home.html")
        self._page.wait_for_load_state("networkidle")

    def students(self) -> list[tuple[str, str]]:
        self._home()
        return parse_students(self._page.content())

    def _select(self, student_id: str) -> None:
        self._home()
        with self._page.expect_navigation():
            self._page.evaluate(f"switchStudent({int(student_id)})")
        self._page.wait_for_load_state("networkidle")

    def classes(self, student_id: str) -> list[tuple[str, object, list[str]]]:
        self._select(student_id)
        links = parse_class_links(self._page.content())
        out = []
        for i, href in enumerate(links, 1):
            out.append(self._one_class(i, len(links), href))
            self._page.wait_for_timeout(500)
        return out

    def _one_class(self, idx: int, total: int, href: str):
        p = self._page
        url = f"{self._creds.base_url}/guardian/{href}"
        try:
            with p.expect_response(
                lambda r: LOOKUP in r.url and r.status == 200, timeout=NAV_TIMEOUT_MS
            ) as info:
                p.goto(url)
            raw = info.value.json()
        except Exception as e:
            log.info("class %d/%d: no assignment data (%s)", idx, total, type(e).__name__)
            return (f"class {idx}", [], [f"class {idx}: assignment lookup failed ({type(e).__name__})"])
        course = parse_course_name(p.content())
        warnings = [] if course else [f"class {idx}: course name not found"]
        log.info("class %d/%d scraped", idx, total)
        return (course or f"class {idx}", raw, warnings)
