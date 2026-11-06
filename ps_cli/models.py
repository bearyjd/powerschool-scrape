"""Immutable data shapes."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Assignment:
    course: str
    title: str
    due: str  # YYYY-MM-DD
    category: str | None = None
    score: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
