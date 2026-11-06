"""Orchestrate scraper + parsers into the JSON contract."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from .parse import classify

log = logging.getLogger("ps")


def _child(scraper, sid: str, name: str, today: date, days: int) -> dict:
    missing, late, upcoming, warnings = [], [], [], []
    for course, raw, class_warnings in scraper.classes(sid):
        r = classify(raw, course, today, days)
        missing += r.missing
        late += r.late
        upcoming += r.upcoming
        warnings += [*class_warnings, *r.warnings]

    def ordered(items):
        seen = {(a.course, a.title, a.due): a for a in items}
        return [a.to_dict() for a in sorted(seen.values(), key=lambda a: (a.due, a.course, a.title))]

    return {"name": name, "student_id": sid, "missing": ordered(missing), "late": ordered(late),
            "upcoming": ordered(upcoming), "warnings": warnings}


def build_summary(scraper, today: date, days: int, child_filter: str | None) -> dict:
    top: list[str] = []
    children: list[dict] = []
    students = scraper.students()
    if not students:
        top.append("no students found on home page")
    selected = [(i, n) for i, n in students if not child_filter or child_filter.lower() in n.lower()]
    if students and not selected:
        top.append("no student matched --child filter")
    for n, (sid, name) in enumerate(selected, 1):
        try:
            child = _child(scraper, sid, name, today, days)
        except Exception as e:
            log.warning("student %d failed: %s", n, type(e).__name__)
            msg = f"student {sid} failed: {type(e).__name__}"
            children.append({"name": name, "student_id": sid, "missing": [], "late": [],
                             "upcoming": [], "warnings": [msg]})
            continue
        children.append(child)
    return {"scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "children": children, "warnings": top}
