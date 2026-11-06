import json
from datetime import date

from ps_cli import cli
from ps_cli.browser import LoginError


class FakeScraper:
    def __init__(self, fail_login=False):
        self.fail_login = fail_login

    def __enter__(self):
        if self.fail_login:
            raise LoginError("login failed")
        return self

    def __exit__(self, *a):
        return False

    def students(self):
        return [("1", "Alex Fake"), ("2", "Sam Fake"), ("3", "Jo Fake")]

    def classes(self, student_id):
        if student_id == "3":
            raise RuntimeError("boom")
        return [("Fake Algebra", [{"_name": "HW", "_assignmentsections": [
            {"duedate": "2026-10-01", "_assignmentscores": [{"ismissing": True}]}]}], [])]


def run(argv, scraper, capsys, monkeypatch):
    monkeypatch.setattr(cli, "make_scraper", lambda: scraper)
    monkeypatch.setattr(cli, "today", lambda: date(2026, 11, 5))
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out


def test_summary_contract(capsys, monkeypatch):
    code, out = run(["summary", "--json"], FakeScraper(), capsys, monkeypatch)
    assert code == 0
    d = json.loads(out.out)
    assert set(d) == {"scraped_at", "children", "warnings"}
    c = d["children"][0]
    assert set(c) == {"name", "student_id", "missing", "late", "upcoming", "warnings"}
    assert c["missing"][0]["due"] == "2026-10-01"
    # failing child becomes a warning, not a crash
    assert d["warnings"] == []
    assert any("student" in w for w in d["children"][2]["warnings"])
    assert len(d["children"]) == 3


def test_child_filter(capsys, monkeypatch):
    code, out = run(["summary", "--json", "--child", "sam"], FakeScraper(), capsys, monkeypatch)
    d = json.loads(out.out)
    assert [c["name"] for c in d["children"]] == ["Sam Fake"]


def test_child_filter_no_match_warns(capsys, monkeypatch):
    code, out = run(["summary", "--child", "zzz"], FakeScraper(), capsys, monkeypatch)
    d = json.loads(out.out)
    assert d["children"] == [] and d["warnings"]


def test_login_failure(capsys, monkeypatch):
    code, out = run(["summary", "--json"], FakeScraper(fail_login=True), capsys, monkeypatch)
    assert code != 0
    d = json.loads(out.out)
    assert d["error"] and d["warnings"] == []


def test_config_error(capsys, monkeypatch):
    from ps_cli.config import ConfigError
    def boom():
        raise ConfigError("no creds")
    monkeypatch.setattr(cli, "make_scraper", boom)
    code = cli.main(["summary"])
    assert code != 0
    assert "no creds" in json.loads(capsys.readouterr().out)["error"]


def test_child_warnings_not_in_top_level(capsys, monkeypatch):
    class S(FakeScraper):
        def classes(self, sid):
            return [("C", [], ["class 1: course name not found"])]
    code, out = run(["summary"], S(), capsys, monkeypatch)
    d = json.loads(out.out)
    assert d["warnings"] == []
    assert d["children"][0]["warnings"] == ["class 1: course name not found"]
