"""Pure parsers: no network, no browser."""
from __future__ import annotations

import html as htmllib
import re
from dataclasses import dataclass
from datetime import date, timedelta

from .models import Assignment

_STUDENT_RE = re.compile(
    r"""<a[^>]*href=["']javascript:switchStudent\((\d+)\);?["'][^>]*>(.*?)</a>""", re.S)
_CLASS_RE = re.compile(r"""href=["']([^"']*scores\.html\?frn=[^"']*)["']""")
_COURSE_TABLE_RE = re.compile(r"<table[^>]*>.*?</table>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class ClassResult:
    missing: tuple[Assignment, ...] = ()
    late: tuple[Assignment, ...] = ()
    upcoming: tuple[Assignment, ...] = ()
    warnings: tuple[str, ...] = ()


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(_TAG_RE.sub("", fragment))).strip()


def _clean(value, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()[:limit].strip()


def parse_students(page_html: str) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for sid, label in _STUDENT_RE.findall(page_html):
        name = _text(label)
        if name and sid not in seen:
            seen[sid] = name
    return list(seen.items())


def parse_class_links(page_html: str) -> list[str]:
    links: list[str] = []
    for href in _CLASS_RE.findall(page_html):
        href = htmllib.unescape(href)
        if "begdate=" in href and href not in links:
            links.append(href)
    return links


def parse_course_name(page_html: str) -> str | None:
    for table in _COURSE_TABLE_RE.findall(page_html):
        if "<th>Course</th>" not in table:
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", table, re.S)
        if cells and _text(cells[0]):
            return _text(cells[0])
    return None


def _score_text(score: dict) -> str | None:
    entered = score.get("actualscoreentered")
    if isinstance(entered, str) and entered.strip():
        return entered.strip()
    points = score.get("scorepoints")
    if isinstance(points, (int, float)) and not isinstance(points, bool):
        return f"{points:g}"
    return None


def _category(section: dict) -> str | None:
    for assoc in section.get("_assignmentcategoryassociations") or []:
        if isinstance(assoc, dict):
            name = (assoc.get("_teachercategory") or {}).get("name")
            if isinstance(name, str) and _clean(name):
                return _clean(name)
    return None


def _flags(scores: list) -> dict:
    flags = {"missing": False, "late": False, "exempt": False,
             "collected": False, "scored": False, "score": None}
    for s in scores:
        if not isinstance(s, dict):
            continue
        flags["missing"] |= bool(s.get("ismissing"))
        flags["late"] |= bool(s.get("islate"))
        flags["exempt"] |= bool(s.get("isexempt"))
        flags["collected"] |= bool(s.get("iscollected"))
        text = _score_text(s)
        if text is not None:
            flags["scored"] = True
            flags["score"] = flags["score"] or text
    return flags


def _parse_due(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def classify(raw, course: str, today: date, days: int) -> ClassResult:
    """Bucket a decoded /ws/xte/assignment/lookup payload."""
    if not isinstance(raw, list):
        return ClassResult(warnings=(f"{course}: unexpected assignment payload",))
    horizon = today + timedelta(days=days)
    buckets: dict[str, dict] = {"missing": {}, "late": {}, "upcoming": {}}
    warnings: list[str] = []
    bad_dates = malformed = 0
    for item in raw:
        sections = item.get("_assignmentsections") if isinstance(item, dict) else None
        if not isinstance(sections, list):
            malformed += 1
            continue
        title = _clean(item.get("_name") or "") or "(untitled)"
        for sec in sections:
            if not isinstance(sec, dict):
                malformed += 1
                continue
            due = _parse_due(sec.get("duedate"))
            if due is None:
                bad_dates += 1
                continue
            scores = sec.get("_assignmentscores")
            f = _flags(scores if isinstance(scores, list) else [])
            a = Assignment(course, title, due.isoformat(), _category(sec), f["score"])
            key = (a.title, a.due)
            if f["missing"] and not f["exempt"]:
                buckets["missing"].setdefault(key, a)
            if f["late"] and not f["exempt"]:
                buckets["late"].setdefault(key, a)
            if (today <= due <= horizon and not (f["collected"] or f["scored"]
                                                 or f["exempt"] or f["missing"])):
                buckets["upcoming"].setdefault(key, a)
    if malformed:
        warnings.append(f"{course}: {malformed} malformed assignment entries skipped")
    if bad_dates:
        warnings.append(f"{course}: {bad_dates} assignments with unparseable due date skipped")

    def ordered(b: dict) -> tuple[Assignment, ...]:
        return tuple(sorted(b.values(), key=lambda a: (a.due, a.title)))

    return ClassResult(ordered(buckets["missing"]), ordered(buckets["late"]),
                       ordered(buckets["upcoming"]), tuple(warnings))
