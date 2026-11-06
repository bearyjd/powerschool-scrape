import json
from datetime import date
from pathlib import Path

from ps_cli.parse import (classify, parse_class_links, parse_course_name,
                          parse_students)

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 5)


def load():
    return json.loads((FIX / "lookup.json").read_text())


def titles(items):
    return [a.title for a in items]


def test_missing_excludes_exempt_and_dedupes():
    r = classify(load(), "Fake Algebra", TODAY, 14)
    assert titles(r.missing) == ["Missing Worksheet"]
    assert r.missing[0].category == "Homework"
    assert r.missing[0].course == "Fake Algebra"
    assert r.missing[0].due == "2026-10-20"


def test_late():
    r = classify(load(), "C", TODAY, 14)
    assert titles(r.late) == ["Late Essay"]
    assert r.late[0].score == "8"


def test_upcoming_window_boundaries_and_sorting():
    r = classify(load(), "C", TODAY, 14)
    assert titles(r.upcoming) == ["Quiz Today", "Test On Boundary"]
    assert [a.due for a in r.upcoming] == ["2026-11-05", "2026-11-19"]


def test_upcoming_excludes_scored_collected_exempt_missing():
    r = classify(load(), "C", TODAY, 30)
    names = titles(r.upcoming)
    for bad in ("Already Scored", "Collected Future", "Exempt Missing",
                "Missing Worksheet", "Yesterday Not Upcoming"):
        assert bad not in names
    assert "Beyond Window" in names


def test_malformed_entries_produce_warnings_not_crash():
    r = classify(load(), "C", TODAY, 14)
    assert any("Bad Date" not in w and "due" in w for w in r.warnings)
    assert any("malformed" in w for w in r.warnings)


def test_empty_and_non_list():
    assert classify([], "C", TODAY, 14).missing == ()
    r = classify({"oops": 1}, "C", TODAY, 14)
    assert r.warnings and not r.missing


def test_sorted_by_due():
    r = classify(load(), "C", TODAY, 14)
    dues = [a.due for a in r.missing + r.late + r.upcoming]
    assert dues[: len(r.missing)] == sorted(dues[: len(r.missing)])


def test_assignment_to_dict_and_frozen():
    a = classify(load(), "C", TODAY, 14).missing[0]
    assert set(a.to_dict()) == {"course", "title", "due", "category", "score"}
    import dataclasses
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.title = "x"


def test_parse_students_dedupes():
    s = parse_students((FIX / "home.html").read_text())
    assert s == [("111", "Alex Fake"), ("222", "Sam Fake"), ("333", "Jo Fake")]


def test_parse_class_links_requires_begdate_and_dedupes():
    links = parse_class_links((FIX / "home.html").read_text())
    assert len(links) == 2
    assert all("begdate=" in h and "&amp;" not in h for h in links)


def test_parse_course_name():
    assert parse_course_name((FIX / "scores.html").read_text()) == "Fake Algebra"
    assert parse_course_name("<html></html>") is None


def test_title_and_category_sanitised_and_capped():
    raw = [{"_name": "Line one\n\n  line   two " + "x" * 300, "_assignmentsections": [
        {"duedate": "2026-10-20", "_assignmentscores": [{"ismissing": True}],
         "_assignmentcategoryassociations": [{"_teachercategory": {"name": "Home\nwork\t"}}]}]}]
    a = classify(raw, "C", TODAY, 14).missing[0]
    assert a.title.startswith("Line one line two xxx") and len(a.title) <= 160
    assert a.category == "Home work"
    assert "\n" not in a.title
