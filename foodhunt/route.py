"""Day planner (slot-based, deterministic).

Each day has eating slots (breakfast → supper). For each slot we pick the place that:
  - fits the slot (a dessert shop is not a breakfast),
  - is open on arrival and stays open for the visit (sell-out places need 1 h margin),
  - is close to where you are (walk if ≤ walk_max_m, else Grab),
  - is not at peak crowd,
  - has the FEWEST other chances to fit (scarcity) — e.g. a Fri–Sun night market wins its slot,
  - is a must-eat.
Same input → same plan, so you can explain every choice.
"""
from __future__ import annotations

import datetime as dt

from . import crowd, geo
from . import hours as H

DEFAULT_HOURS = H.parse_simple("10:00-21:00")  # ONLY when hours are unknown (flagged in output)

# name, start, end, kinds allowed
SLOTS = [
    ("Breakfast", "06:30", "09:30", {"breakfast", "meal", "snack"}),
    ("Morning snack", "09:30", "11:15", {"dessert", "snack", "mall", "meal"}),
    ("Lunch", "11:30", "13:45", {"meal", "hotpot"}),
    ("Afternoon", "14:00", "17:00", {"dessert", "snack", "mall"}),
    ("Dinner", "17:00", "19:45", {"meal", "hotpot", "night_market"}),
    ("Supper", "19:45", "22:30", {"night_market", "dessert", "meal", "hotpot"}),
]


def _est_leg(a, b, walk_max_m):
    d = geo.haversine_m(a, b) * 1.3
    if d <= walk_max_m:
        return "walking", max(1, round(d / 75))
    return "driving", max(5, round(d / 300) + 5)  # +5 min to get a Grab


def _fit(p: dict, wd: int, arrive: int, s_start: int, s_end: int) -> tuple[int, tuple[int, int]] | None:
    """Earliest start time inside the slot when p is open long enough, else None."""
    hrs = p["_hours"] or DEFAULT_HOURS
    begin = max(arrive, s_start, H._mins(p["not_before"]) if p.get("not_before") else 0)
    win = H.open_window(hrs, wd, begin)
    if not win:
        return None
    begin = max(begin, win[0])
    dwell = p.get("dwell", 40)
    last_in = win[1] - (60 if p.get("sells_out") else 15)
    if begin > s_end or begin > last_in or begin + dwell > win[1]:
        return None
    return begin, win


def _chances(p: dict, days: list[tuple[int, int, int]], slots) -> int:
    """How many (day, slot) pairs could host p at all — fewer = schedule it first."""
    n = 0
    for wd, d_start, d_end in days:
        for _, a, b, kinds in slots:
            if p.get("kind", "meal") in kinds and _fit(p, wd, max(d_start, H._mins(a)), H._mins(a), min(H._mins(b), d_end)):
                n += 1
    return n


def _slots_today(p: dict, wd: int, d_start: int, d_end: int, slots) -> list[str]:
    return [n for n, a, b, kinds in slots if p.get("kind", "meal") in kinds
            and _fit(p, wd, max(d_start, H._mins(a)), H._mins(a), min(H._mins(b), d_end))]


def plan(trip: dict, places: list[dict], fetch_routes: bool = True):
    start = trip["start"]
    walk_max = trip.get("walk_max_m", 1200)
    todo = [p for p in places if p.get("lat") is not None]
    per_day = min(trip.get("max_stops_per_day", 6), -(-len(todo) // max(1, len(trip["days"]))) + 1)
    slots = [(n, a, b, set(k)) for n, a, b, k in trip.get("slots", SLOTS)]
    day_info = []
    for day in trip["days"]:
        date = dt.date.fromisoformat(str(day["date"]))
        day_info.append((date, H._mins(day.get("start_time", "07:00")), H._mins(day.get("end_time", "23:00"))))
    days_out = []

    for di, (date, d_start, d_end) in enumerate(day_info):
        wd = date.weekday()
        later = [(d.weekday(), s, e) for d, s, e in day_info[di:]]
        t, here, stops = d_start, (start["lat"], start["lng"]), []
        # "Today or never": places whose only remaining chances are today (e.g. a Fri–Sun night
        # market on the last Friday). Reserve room for them so earlier slots can't use up the day.
        today_slots = {id(p): _slots_today(p, wd, d_start, d_end, slots) for p in todo}
        forced = [p for p in todo if today_slots[id(p)] and _chances(p, later, slots) == len(today_slots[id(p)])]

        for slot_name, a, b, kinds in slots:
            s_start, s_end = H._mins(a), min(H._mins(b), d_end)
            if len(stops) >= per_day or t > s_end:
                continue
            waiting = [p for p in forced if p in todo]
            only_forced = len(stops) + len(waiting) >= per_day
            best = None
            for p in todo:
                if p.get("kind", "meal") not in kinds:
                    continue
                if only_forced and p not in waiting:
                    continue
                mode, travel = _est_leg(here, (p["lat"], p["lng"]), walk_max)
                f = _fit(p, wd, t + travel, s_start, s_end)
                if not f:
                    continue
                begin, win = f
                hrs = p["_hours"] or DEFAULT_HOURS
                cr = crowd.estimate(p.get("kind", "meal"), hrs, wd, p.get("reviews"))[min(23, begin // 60)]
                scarcity = 120 / max(1, _chances(p, later, slots))
                score = (travel + 0.3 * max(0, begin - t - travel) + 0.4 * cr - scarcity
                         - (30 if p.get("must") else 0) - (20 if p.get("sells_out") else 0))
                if best is None or score < best[0]:
                    best = (score, p, mode, travel, begin, cr, win)
            if not best:
                continue
            _, p, mode, travel, begin, cr, win = best
            todo.remove(p)
            dwell = p.get("dwell", 40)
            leg = geo.route_leg(here, (p["lat"], p["lng"]), mode) if fetch_routes else {
                "mode": mode, "minutes": travel, "meters": None, "steps": [], "geometry": [], "source": "estimate"}
            hrs = p["_hours"]
            stops.append({
                "slot": slot_name, "place": p, "leg": leg,
                "arrive": H.fmt(begin), "leave": H.fmt(begin + dwell),
                "wait_min": max(0, begin - (t + leg["minutes"])),
                "wait_reason": "opening" if begin == win[0] else "free time",
                "hours_today": H.describe(hrs, wd), "hours_known": hrs is not None,
                "crowd_now": cr, "crowd": crowd.for_place(p, hrs or DEFAULT_HOURS, wd),
            })
            t, here = begin + dwell, (p["lat"], p["lng"])

        pts = [(start["lat"], start["lng"])] + [(s["place"]["lat"], s["place"]["lng"]) for s in stops]
        days_out.append({
            "date": date.isoformat(), "weekday": date.strftime("%a"), "stops": stops,
            "map_link": geo.gmaps_dir_link(pts, "walking" if all(s["leg"]["mode"] == "walking" for s in stops) else "driving"),
        })

    return days_out, todo  # todo = didn't fit (closed on these days / no free slot)
