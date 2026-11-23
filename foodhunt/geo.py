"""Geocoding + routing. Google if GOOGLE_MAPS_API_KEY is set, else free OSM services."""
from __future__ import annotations

import math
import os
import time
import urllib.parse

import httpx

UA = {"User-Agent": "foodhunt-local/0.1 (personal trip planner)"}
_last_nominatim = 0.0


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def geocode_osm(query: str) -> dict | None:
    """Nominatim (OSM). Policy: max 1 req/s, identify the client."""
    global _last_nominatim
    wait = 1.1 - (time.time() - _last_nominatim)
    if wait > 0:
        time.sleep(wait)
    _last_nominatim = time.time()
    r = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"format": "jsonv2", "limit": 1, "q": query, "extratags": 1},
        headers=UA, timeout=20,
    )
    r.raise_for_status()
    js = r.json()
    if not js:
        return None
    x = js[0]
    return {
        "lat": float(x["lat"]), "lng": float(x["lon"]),
        "address": x.get("display_name"),
        "opening_hours": (x.get("extratags") or {}).get("opening_hours"),
        "source": "openstreetmap",
    }


def decode_plus_code(code: str, ref: tuple[float, float]) -> tuple[float, float] | None:
    """Decode a short Plus Code like '2F4C+9JR' relative to a reference point (e.g. city centre)."""
    from openlocationcode import openlocationcode as olc

    code = code.strip().split()[0]
    if not olc.isValid(code):
        return None
    full = olc.recoverNearest(code, ref[0], ref[1]) if olc.isShort(code) else code
    area = olc.decode(full)
    return (area.latitudeCenter, area.longitudeCenter)


def route_leg(a: tuple[float, float], b: tuple[float, float], mode: str = "walking") -> dict:
    """Distance/duration + turn-by-turn steps. OSRM (routing.openstreetmap.de) for foot/car.

    Falls back to straight-line x1.3 if the router is unreachable.
    """
    profile = {"walking": ("routed-foot", "foot"), "driving": ("routed-car", "driving")}[mode]
    url = (
        f"https://routing.openstreetmap.de/{profile[0]}/route/v1/{profile[1]}/"
        f"{a[1]},{a[0]};{b[1]},{b[0]}?overview=full&geometries=geojson&steps=true"
    )
    try:
        r = httpx.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        route = r.json()["routes"][0]
        steps = []
        for leg in route["legs"]:
            for s in leg["steps"]:
                text = _step_text(s)
                if text:
                    steps.append(text)
        return {
            "mode": mode,
            "meters": round(route["distance"]),
            "minutes": max(1, round(route["duration"] / 60)),
            "steps": steps,
            "geometry": route["geometry"]["coordinates"],  # [lng, lat]
            "source": "osrm",
        }
    except Exception as e:  # router down → estimate, but say so
        d = haversine_m(a, b) * 1.3
        speed = 75 if mode == "walking" else 300  # m/min (4.5 km/h walk, ~18 km/h city traffic)
        return {
            "mode": mode, "meters": round(d), "minutes": max(1, round(d / speed)),
            "steps": [], "geometry": [[a[1], a[0]], [b[1], b[0]]],
            "source": f"estimate ({type(e).__name__})",
        }


def _step_text(s: dict) -> str | None:
    m = s["maneuver"]
    kind, mod = m.get("type"), m.get("modifier", "")
    road = s.get("name") or "the road"
    dist = round(s.get("distance", 0))
    if kind == "depart":
        return f"Start heading {_bearing(m.get('bearing_after', 0))} on {road} ({dist} m)"
    if kind == "arrive":
        side = f" — it's on your {mod}" if mod in ("left", "right") else ""
        return f"Arrive{side}"
    if dist < 5 and kind not in ("turn",):
        return None
    verb = {"turn": "Turn", "new name": "Continue", "continue": "Continue", "end of road": "At the end of the road turn",
            "fork": "Keep", "roundabout": "At the roundabout take exit", "rotary": "At the roundabout take exit"}.get(kind, "Go")
    if kind in ("roundabout", "rotary"):
        return f"{verb} {m.get('exit', '')} onto {road} ({dist} m)"
    return f"{verb} {mod} onto {road} ({dist} m)".replace("  ", " ")


def _bearing(deg: float) -> str:
    return ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][round(deg / 45) % 8]


def gmaps_dir_link(points: list[tuple[float, float]], mode: str = "walking") -> str:
    """Google Maps directions URL (origin, up to 9 waypoints, destination). Opens the app on phones."""
    pts = [f"{p[0]:.6f},{p[1]:.6f}" for p in points]
    q = {"api": "1", "origin": pts[0], "destination": pts[-1], "travelmode": mode}
    if len(pts) > 2:
        q["waypoints"] = "|".join(pts[1:-1][:9])
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(q, safe="|,")


def gmaps_place_link(name: str, place_id: str | None = None) -> str:
    q = {"api": "1", "query": name}
    if place_id:
        q["query_place_id"] = place_id
    return "https://www.google.com/maps/search/?" + urllib.parse.urlencode(q)


def has_google() -> bool:
    return bool(os.getenv("GOOGLE_MAPS_API_KEY"))
