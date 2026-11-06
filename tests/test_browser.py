from pathlib import Path
from unittest.mock import MagicMock

from ps_cli.browser import PlaywrightScraper, LoginError
from ps_cli.config import Credentials
import pytest


def test_missing_playwright_gives_login_error(monkeypatch):
    import builtins
    real = builtins.__import__
    def fake(name, *a, **k):
        if name.startswith("playwright"):
            raise ImportError("no")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    s = PlaywrightScraper(Credentials("u", "p", "https://x.powerschool.com"))
    with pytest.raises(LoginError) as e:
        s.__enter__()
    assert "p" != str(e.value)



FIX = Path(__file__).parent / "fixtures"


def scraper_with_page(page):
    s = PlaywrightScraper(Credentials("u", "p", "https://x.powerschool.com"))
    s._page = page
    return s


def test_login_rejects_when_not_on_guardian():
    page = MagicMock()
    page.url = "https://x.powerschool.com/public/home.html"
    with pytest.raises(LoginError):
        scraper_with_page(page)._login()
    page.fill.assert_any_call("#fieldAccount", "u")


def test_login_ok():
    page = MagicMock()
    page.url = "https://x.powerschool.com/guardian/home.html"
    scraper_with_page(page)._login()
    page.click.assert_called_with("#btn-enter-sign-in")


def test_students_and_classes_and_one_class():
    page = MagicMock()
    home = (FIX / "home.html").read_text()
    page.content.side_effect = [home, home, (FIX / "scores.html").read_text(),
                                "<html></html>"]
    info = MagicMock()
    info.value.json.return_value = [{"x": 1}]
    page.expect_response.return_value.__enter__.return_value = info
    s = scraper_with_page(page)
    assert [n for _, n in s.students()][0] == "Alex Fake"
    res = s.classes("111")
    assert [c[0] for c in res] == ["Fake Algebra", "class 2"]
    assert res[1][2] == ["class 2: course name not found"]
    page.evaluate.assert_called_with("switchStudent(111)")


def test_one_class_lookup_failure_is_warning():
    page = MagicMock()
    page.expect_response.side_effect = TimeoutError("t")
    name, raw, warns = scraper_with_page(page)._one_class(1, 1, "scores.html?frn=1&begdate=x")
    assert raw == [] and "TimeoutError" in warns[0]


def test_exit_is_safe_and_enter_wraps_errors(monkeypatch):
    s = PlaywrightScraper(Credentials("u", "p", "https://x.powerschool.com"))
    assert s.__exit__() is False
    import sys
    import types
    mod = types.ModuleType("playwright.sync_api")
    def boom():
        raise RuntimeError("secret p")
    mod.sync_playwright = boom
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", mod)
    with pytest.raises(LoginError) as e:
        s.__enter__()
    assert "secret" not in str(e.value)


def test_login_refuses_to_fill_on_wrong_host():
    page = MagicMock()
    page.url = "https://evil.example.com/public/"
    with pytest.raises(LoginError):
        scraper_with_page(page)._login()
    page.fill.assert_not_called()


def test_login_refuses_http_page():
    page = MagicMock()
    page.url = "http://x.powerschool.com/public/"
    with pytest.raises(LoginError):
        scraper_with_page(page)._login()
    page.fill.assert_not_called()


def test_login_rejects_post_login_redirect_off_host():
    page = MagicMock()
    urls = iter(["https://x.powerschool.com/public/"])
    type(page).url = property(lambda self: next(urls, "https://evil.example.com/guardian/home.html"))
    with pytest.raises(LoginError):
        scraper_with_page(page)._login()
