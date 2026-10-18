"""Europe/Warsaw wall time for the route engine (`real_engine._clock`). No files, no HTTP.

The Python transit planner that lived here was removed: transit trips come from the router's `POST /plan`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _last_sunday(year: int, month: int) -> int:
    if month == 12:
        last = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = datetime(year, month + 1, 1) - timedelta(days=1)
    return last.day - (last.weekday() - 6) % 7


def warsaw_offset(moment: datetime) -> timedelta:
    """Poland civil offset: UTC+2 from the last Sunday of March 01:00 UTC, else UTC+1."""
    utc = moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    start = datetime(utc.year, 3, _last_sunday(utc.year, 3), 1, tzinfo=timezone.utc)
    end = datetime(utc.year, 10, _last_sunday(utc.year, 10), 1, tzinfo=timezone.utc)
    return timedelta(hours=2) if start <= utc < end else timedelta(hours=1)


def as_warsaw(now: datetime) -> datetime:
    """Naive Europe/Warsaw wall time. A naive input is already treated as Warsaw."""
    if now.tzinfo is None:
        return now
    utc = now.astimezone(timezone.utc)
    return (utc + warsaw_offset(utc)).replace(tzinfo=None)
