"""Display every time in Kuala Lumpur time (MYT, UTC+8) — the traveller's home clock.

The planner works in the destination's local time (shops open by *their* clock). We only shift
at the edges: what the user reads (UI, Notion) is MYT, with local time shown alongside.
Photo matching keeps local time, because phones switch to the local zone abroad.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from zoneinfo import ZoneInfo

DISPLAY_TZ = os.getenv("FOODHUNT_DISPLAY_TZ", "Asia/Kuala_Lumpur")
DISPLAY_LABEL = os.getenv("FOODHUNT_DISPLAY_LABEL", "MYT")
_HHMM = re.compile(r"\b(\d{2}):(\d{2})\b")


def shift_minutes(local_tz: str | None, date: str | dt.date | None = None) -> int:
    """display offset − local offset, e.g. Hat Yai (UTC+7) → KL (UTC+8) = +60."""
    d = dt.date.fromisoformat(str(date)) if date else dt.date.today()
    noon = dt.datetime.combine(d, dt.time(12))
    local = ZoneInfo(local_tz or DISPLAY_TZ).utcoffset(noon)
    disp = ZoneInfo(DISPLAY_TZ).utcoffset(noon)
    return int((disp - local).total_seconds() // 60)


def shift_hhmm(hhmm: str, minutes: int) -> str:
    h, m = map(int, hhmm.split(":"))
    t = (h * 60 + m + minutes) % 1440
    return f"{t // 60:02d}:{t % 60:02d}"


def shift_text(text: str, minutes: int) -> str:
    """Shift every HH:MM inside a string ('06:30–14:30' → '07:30–15:30')."""
    if not minutes or not text:
        return text
    return _HHMM.sub(lambda m: shift_hhmm(m.group(0), minutes), text)


def now_display() -> str:
    return dt.datetime.now(ZoneInfo(DISPLAY_TZ)).isoformat(timespec="seconds")
