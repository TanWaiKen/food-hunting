"""Crowd level by hour (0-100).

1. BestTime.app forecast when BESTTIME_API_KEY_PRIVATE is set (real foot-traffic data).
2. Otherwise a labelled ESTIMATE: meal-time curves by place kind, limited to opening hours.
   Google's "Popular times" is NOT available in the official Places API, so we never claim it.
"""
from __future__ import annotations

import math
import os

import httpx

from . import hours as H

# kind → list of (peak_hour, width_hours, weight)
CURVES: dict[str, list[tuple[float, float, float]]] = {
    "breakfast": [(8.0, 1.2, 1.0)],
    "meal": [(12.5, 1.0, 1.0), (18.8, 1.2, 0.9)],
    "dessert": [(15.0, 1.5, 0.8), (20.5, 1.2, 1.0)],
    "night_market": [(19.5, 1.3, 1.0)],
    "mall": [(14.0, 2.0, 0.7), (19.0, 1.5, 1.0)],
    "hotpot": [(19.0, 1.3, 1.0), (12.5, 1.0, 0.5)],
    "snack": [(12.5, 1.5, 0.6), (17.5, 1.5, 0.8)],
}


def besttime(name: str, address: str) -> list[list[int]] | None:
    key = os.getenv("BESTTIME_API_KEY_PRIVATE")
    if not key:
        return None
    r = httpx.post("https://besttime.app/api/v1/forecasts", timeout=60,
                   params={"api_key_private": key, "venue_name": name, "venue_address": address})
    js = r.json()
    if js.get("status") != "OK":
        return None
    # BestTime day_int 0=Mon; day_raw is 24 values starting at 6am
    week = [[0] * 24 for _ in range(7)]
    for day in js["analysis"]:
        d = day["day_info"]["day_int"]
        for i, v in enumerate(day["day_raw"]):
            week[d][(6 + i) % 24] = v
    return week


def estimate(kind: str, hrs: H.Hours | None, weekday: int, popularity: int | None) -> list[int]:
    curve = CURVES.get(kind, CURVES["meal"])
    weekend = 1.15 if weekday >= 4 else 1.0  # Fri-Sun busier (Malaysian weekend crowd in Hat Yai)
    pop = 0.6 + 0.4 * min(1.0, math.log10((popularity or 100) + 1) / 4)  # 10k reviews ≈ 1.0
    out = []
    for h in range(24):
        t = h + 0.5
        v = sum(w * math.exp(-((t - p) ** 2) / (2 * s * s)) for p, s, w in curve)
        open_now = hrs is None or any(o <= h * 60 + 30 < c for o, c in hrs.get(weekday, []))
        out.append(round(min(100, 100 * v * weekend * pop)) if open_now else 0)
    return out


def summarize(by_hour: list[int], hrs: H.Hours | None, weekday: int, sells_out: bool = False) -> dict:
    windows = (hrs or {}).get(weekday) or [(6 * 60, 23 * 60)]
    open_hours = [h for h in range(24) if any(o <= h * 60 + 30 < c for o, c in windows)]
    if not open_hours:
        return {"best": None, "peak": None, "note": "closed"}
    peak = max(open_hours, key=lambda h: by_hour[h])
    # best = quietest open hour; if it sells out, prefer the first 2 open hours
    # never recommend the last hour (kitchen closing / stalls packing up)
    usable = open_hours[:-1] if len(open_hours) > 2 else open_hours
    pool = usable[:2] if sells_out else usable
    best = min(pool, key=lambda h: (by_hour[h], h))
    return {
        "best": f"{best:02d}:00–{best + 1:02d}:00",
        "peak": f"{peak:02d}:00–{peak + 1:02d}:00",
        "best_hour": best, "peak_hour": peak,
        "note": "go early — sells out" if sells_out else "",
    }


def for_place(p: dict, hrs: H.Hours | None, weekday: int) -> dict:
    real = besttime(p["name"], p.get("address") or "") if p.get("address") else None
    if real:
        by_hour, src = real[weekday], "besttime"
    else:
        by_hour, src = estimate(p.get("kind", "meal"), hrs, weekday, p.get("reviews")), "estimate"
    s = summarize(by_hour, hrs, weekday, p.get("sells_out", False))
    return {**s, "by_hour": by_hour, "source": src}


def has_besttime() -> bool:
    return bool(os.getenv("BESTTIME_API_KEY_PRIVATE"))
