"""Times are planned in local time but shown in Kuala Lumpur time (MYT)."""
from foodhunt import photos, render, route, tz
from foodhunt import hours as H


def test_shift_bangkok_to_kl_is_plus_one_hour():
    assert tz.shift_minutes("Asia/Bangkok", "2026-12-04") == 60
    assert tz.shift_minutes("Asia/Kuala_Lumpur", "2026-12-04") == 0
    assert tz.shift_minutes("Asia/Tokyo", "2026-12-04") == -60
    assert tz.shift_text("06:30–14:30", 60) == "07:30–15:30"
    assert tz.shift_hhmm("23:30", 60) == "00:30"


def test_view_shows_myt_and_keeps_local():
    trip = {"trip": "T", "city": "Hat Yai", "timezone": "Asia/Bangkok",
            "start": {"name": "H", "lat": 7.0058, "lng": 100.4717},
            "days": [{"date": "2026-12-04", "start_time": "06:30"}]}
    p = {"name": "Pork leg", "kind": "breakfast", "hours": "06:30-14:30", "lat": 7.003, "lng": 100.4728,
         "_hours": H.parse_simple("06:30-14:30"), "sells_out": True}
    days, left = route.plan(trip, [p], fetch_routes=False)
    v = render.view_model(trip, days, left)
    s = v["days"][0]["stops"][0]
    assert v["trip"]["time"]["shift_min"] == 60 and v["trip"]["time"]["label"] == "MYT"
    assert s["arrive"] == tz.shift_hhmm(s["arrive_local"], 60)
    assert s["hours_today"] == "07:30–15:30" and s["hours_local"] == "06:30–14:30"
    md = render.notion_md(trip, days, left)
    assert "Kuala Lumpur time (MYT)" in md and f"{s['arrive']} MYT" in md
    # photo matching stays on the destination clock (phones switch zones abroad)
    idx = photos.stop_index(v)
    assert idx[0]["arrive"] == s["arrive_local"]
