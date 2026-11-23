"""Planner, hours, crowd and rendering — all offline (no network)."""
import datetime as dt

import pytest

from foodhunt import crowd, render, route
from foodhunt import hours as H


# ---------- hours ----------

@pytest.mark.parametrize("spec,day,expect", [
    ("06:30-14:30", 0, [(390, 870)]),
    ("Mo,Tu,Th-Su 11:00-20:00; We off", 2, []),
    ("Mo,Tu,Th-Su 11:00-20:00; We off", 3, [(660, 1200)]),
    ("10:00-14:00,16:00-20:00", 5, [(600, 840), (960, 1200)]),
    ("Fr-Su 17:00-24:00", 4, [(1020, 1440)]),
    ("Fr-Su 17:00-24:00", 1, []),
    ("18:00-02:00", 0, [(1080, 1560)]),          # past midnight
])
def test_parse_simple(spec, day, expect):
    assert H.parse_simple(spec)[day] == expect


def test_unknown_format_is_none():
    assert H.parse_simple("daily lunch time") is None


def test_google_periods():
    periods = [{"open": {"day": 0, "hour": 9, "minute": 0}, "close": {"day": 0, "hour": 17, "minute": 0}}]  # Sunday
    assert H.from_google(periods)[6] == [(540, 1020)]


# ---------- crowd ----------

def test_crowd_zero_when_closed_and_best_not_last_hour():
    hrs = H.parse_simple("17:00-24:00")
    by = crowd.estimate("night_market", hrs, 4, 1500)
    assert all(v == 0 for v in by[:17])
    s = crowd.summarize(by, hrs, 4)
    assert s["best_hour"] != 23 and s["peak_hour"] == 19


# ---------- planner ----------

def _p(name, kind, hours, lat, lng, **kw):
    return {"name": name, "kind": kind, "hours": hours, "lat": lat, "lng": lng,
            "_hours": H.parse_simple(hours) if hours else None, **kw}


TRIP = {
    "start": {"name": "Hotel", "lat": 7.0058, "lng": 100.4717},
    "days": [{"date": "2026-12-04", "start_time": "06:30", "end_time": "23:30"},   # Fri
             {"date": "2026-12-07", "start_time": "06:30", "end_time": "23:30"}],  # Mon
    "max_stops_per_day": 6,
}


def _places():
    return [
        _p("Pork leg", "breakfast", "06:30-14:30", 7.0030, 100.4728, sells_out=True),
        _p("Noodles", "meal", "07:30-15:30", 7.0068, 100.4723),
        _p("Lunch house", "meal", "Mo,Tu,Th-Su 11:00-20:00; We off", 7.0074, 100.4745),
        _p("Night market", "night_market", "Fr-Su 17:00-24:00", 7.0060, 100.4715, not_before="18:00"),
        _p("Ice cream", "dessert", "11:30-21:00", 6.9987, 100.4695),
    ]


def test_every_stop_is_open_and_night_market_only_on_its_days():
    days, left = route.plan(TRIP, _places(), fetch_routes=False)
    seen = []
    for d in days:
        wd = dt.date.fromisoformat(d["date"]).weekday()
        for s in d["stops"]:
            p, t = s["place"], H._mins(s["arrive"])
            assert any(o <= t and t + p.get("dwell", 40) <= c for o, c in p["_hours"][wd]), p["name"]
            if p.get("not_before"):
                assert t >= H._mins(p["not_before"])
            seen.append((p["name"], wd))
    assert ("Night market", 4) in seen                     # Friday
    assert all(n != "Night market" or wd in (4, 5, 6) for n, wd in seen)
    assert len({n for n, _ in seen}) == len(seen)           # no duplicates
    assert not left


def test_sells_out_place_gets_breakfast_slot():
    days, _ = route.plan(TRIP, _places(), fetch_routes=False)
    first = days[0]["stops"][0]
    assert first["place"]["name"] == "Pork leg" and first["slot"] == "Breakfast"


def test_places_without_coordinates_are_not_routed():
    ps = _places() + [{"name": "Mystery", "kind": "meal", "lat": None, "lng": None, "_hours": None}]
    days, _ = route.plan(TRIP, ps, fetch_routes=False)
    assert "Mystery" not in [s["place"]["name"] for d in days for s in d["stops"]]


# ---------- render ----------

def test_notion_md_blocks_and_view_model():
    days, left = route.plan(TRIP, _places(), fetch_routes=False)
    trip = {**TRIP, "trip": "Test Trip", "city": "Hat Yai"}
    md = render.notion_md(trip, days, left, [])
    assert "## Day 1" in md and "<toggle>" in md
    assert "\n\n### 1." in md                                # blank line before each block
    view = render.view_model(trip, days, left, [])
    s = view["days"][0]["stops"][0]
    assert {"arrive", "crowd", "leg", "place"} <= s.keys()
    assert len(s["crowd"]["by_hour"]) == 24 and "_hours" not in s["place"]
