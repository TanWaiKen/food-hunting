"""Opening hours → {weekday(0=Mon): [(open_min, close_min), ...]}.

Accepts: Google Places `regularOpeningHours.periods`, OSM `opening_hours` strings
(common forms only), or a simple trip-file string like "06:30-12:00" / "Mo-Sa 10:00-22:00; Su off".
"""
from __future__ import annotations

import re

DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
Hours = dict[int, list[tuple[int, int]]]


def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def parse_simple(spec: str | None) -> Hours | None:
    if not spec:
        return None
    spec = spec.strip()
    if spec == "24/7":
        return {d: [(0, 1440)] for d in range(7)}
    out: Hours = {d: [] for d in range(7)}
    for rule in [r.strip() for r in spec.split(";") if r.strip()]:
        m = re.match(r"^([A-Za-z,\- ]+?)?\s*((?:\d{1,2}:\d{2}-\d{1,2}:\d{2}[, ]*)+|off|closed)$", rule)
        if not m:
            return None  # unknown format → caller treats as "unknown hours"
        days = _expand_days(m.group(1)) if m.group(1) else list(range(7))
        if m.group(2) in ("off", "closed"):
            for d in days:
                out[d] = []
            continue
        ranges = re.findall(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", m.group(2))
        for d in days:
            out[d] = []
            for a, b in ranges:
                o, c = _mins(a), _mins(b)
                out[d].append((o, c if c > o else c + 1440))  # past midnight
    return out


def _expand_days(s: str) -> list[int]:
    days: list[int] = []
    for part in s.replace(" ", "").split(","):
        if "-" in part:
            a, b = part.split("-")
            i, j = DAYS.index(a[:2].title()), DAYS.index(b[:2].title())
            days += list(range(i, j + 1)) if i <= j else list(range(i, 7)) + list(range(0, j + 1))
        elif part:
            days.append(DAYS.index(part[:2].title()))
    return days


def from_google(periods: list[dict] | None) -> Hours | None:
    if not periods:
        return None
    out: Hours = {d: [] for d in range(7)}
    for p in periods:
        o = p.get("open", {})
        c = p.get("close")
        gday = o.get("day", 0)  # Google: 0 = Sunday
        d = (gday - 1) % 7
        om = o.get("hour", 0) * 60 + o.get("minute", 0)
        if c is None:
            out[d].append((0, 1440))
            continue
        cm = c.get("hour", 0) * 60 + c.get("minute", 0)
        if c.get("day", gday) != gday:
            cm += 1440
        out[d].append((om, cm))
    return out


def open_window(hours: Hours | None, weekday: int, t: int) -> tuple[int, int] | None:
    """The window containing minute-of-day t, or the next window later that day."""
    if hours is None:
        return None
    for o, c in sorted(hours.get(weekday, [])):
        if t < c:
            return (o, c)
    return None


def fmt(m: int) -> str:
    m %= 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def describe(hours: Hours | None, weekday: int) -> str:
    if hours is None:
        return "hours unknown — check before going"
    w = hours.get(weekday, [])
    if not w:
        return "CLOSED this day"
    return ", ".join(f"{fmt(o)}–{fmt(c)}" for o, c in w)
