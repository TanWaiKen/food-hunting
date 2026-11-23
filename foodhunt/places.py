"""Place lookup: Google Places API (New) when a key is set, OpenStreetMap otherwise."""
from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path

import httpx

from . import geo, hours

G_BASE = "https://places.googleapis.com/v1"
G_FIELDS = ",".join(
    f"places.{f}" for f in [
        "id", "displayName", "formattedAddress", "location", "rating", "userRatingCount",
        "regularOpeningHours", "photos", "googleMapsUri", "priceLevel", "primaryTypeDisplayName",
        "businessStatus",
    ]
)


def _gkey() -> str:
    return os.environ["GOOGLE_MAPS_API_KEY"]


def google_text_search(query: str, near: tuple[float, float] | None = None, radius_m: int = 5000, limit: int = 5) -> list[dict]:
    body: dict = {"textQuery": query, "pageSize": limit}
    if near:
        body["locationBias"] = {"circle": {"center": {"latitude": near[0], "longitude": near[1]}, "radius": radius_m}}
    r = httpx.post(f"{G_BASE}/places:searchText", json=body, timeout=20,
                   headers={"X-Goog-Api-Key": _gkey(), "X-Goog-FieldMask": G_FIELDS})
    r.raise_for_status()
    return [_from_google(p) for p in r.json().get("places", [])]


def google_nearby(lat: float, lng: float, radius_m: int = 800, types: list[str] | None = None, limit: int = 20) -> list[dict]:
    body = {
        "includedTypes": types or ["restaurant", "cafe", "bakery", "food_court", "dessert_shop"],
        "maxResultCount": min(limit, 20),
        "rankPreference": "POPULARITY",
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius_m}},
    }
    r = httpx.post(f"{G_BASE}/places:searchNearby", json=body, timeout=20,
                   headers={"X-Goog-Api-Key": _gkey(), "X-Goog-FieldMask": G_FIELDS})
    r.raise_for_status()
    return [_from_google(p) for p in r.json().get("places", [])]


def google_photo_uri(photo_name: str, max_px: int = 800) -> str | None:
    """Short-lived URL — download it (save_photo) if it must last, e.g. for Notion."""
    r = httpx.get(f"{G_BASE}/{photo_name}/media", timeout=20,
                  params={"maxWidthPx": max_px, "skipHttpRedirect": "true", "key": _gkey()})
    if r.status_code != 200:
        return None
    return r.json().get("photoUri")


def save_photo(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = httpx.get(url, timeout=30, follow_redirects=True, headers=geo.UA)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def _from_google(p: dict) -> dict:
    loc = p.get("location", {})
    roh = p.get("regularOpeningHours") or {}
    return {
        "name": (p.get("displayName") or {}).get("text"),
        "place_id": p.get("id"),
        "address": p.get("formattedAddress"),
        "lat": loc.get("latitude"), "lng": loc.get("longitude"),
        "rating": p.get("rating"), "reviews": p.get("userRatingCount"),
        "type": (p.get("primaryTypeDisplayName") or {}).get("text"),
        "price_level": p.get("priceLevel"),
        "status": p.get("businessStatus"),
        "hours_text": roh.get("weekdayDescriptions"),
        "hours_periods": roh.get("periods"),
        "photos": [ph["name"] for ph in (p.get("photos") or [])[:3]],
        "maps_url": p.get("googleMapsUri"),
        "source": "google_places",
    }


# ---------- OpenStreetMap fallback (no key) ----------

def osm_lookup(name: str, city: str) -> dict | None:
    g = geo.geocode_osm(f"{name}, {city}")
    if not g:
        return None
    return {"name": name, **g, "maps_url": geo.gmaps_place_link(f"{name} {city}")}


def osm_nearby(lat: float, lng: float, radius_m: int = 800, limit: int = 30) -> list[dict]:
    """Food places around a point from Overpass. Free, but ratings/photos are not in OSM."""
    q = f"""[out:json][timeout:25];
    nwr(around:{radius_m},{lat},{lng})[amenity~"^(restaurant|cafe|fast_food|food_court|ice_cream)$"];
    out center {limit};"""
    r = httpx.post("https://overpass-api.de/api/interpreter", data={"data": q}, headers=geo.UA, timeout=40)
    r.raise_for_status()
    out = []
    for e in r.json().get("elements", []):
        t = e.get("tags", {})
        la = e.get("lat") or e.get("center", {}).get("lat")
        lo = e.get("lon") or e.get("center", {}).get("lon")
        nm = t.get("name:en") or t.get("name")
        if not nm or la is None:
            continue
        out.append({
            "name": nm, "name_local": t.get("name"), "lat": la, "lng": lo,
            "type": t.get("cuisine") or t.get("amenity"),
            "opening_hours": t.get("opening_hours"),
            "distance_m": round(geo.haversine_m((lat, lng), (la, lo))),
            "maps_url": geo.gmaps_place_link(nm),
            "source": "openstreetmap",
        })
    return sorted(out, key=lambda x: x["distance_m"])


# ---------- unified ----------

def lookup(name: str, city: str, near: tuple[float, float] | None = None) -> dict | None:
    if geo.has_google():
        res = google_text_search(f"{name} {city}", near=near, limit=1)
        return res[0] if res else None
    return osm_lookup(name, city)


def nearby(lat: float, lng: float, radius_m: int = 800) -> list[dict]:
    return google_nearby(lat, lng, radius_m) if geo.has_google() else osm_nearby(lat, lng, radius_m)


def parse_hours(place: dict) -> hours.Hours | None:
    if place.get("hours"):
        return hours.parse_simple(place["hours"])
    if place.get("hours_periods"):
        return hours.from_google(place["hours_periods"])
    return hours.parse_simple(place.get("opening_hours"))


def resolve_share_link(url: str) -> dict:
    """share.google / maps.app.goo.gl → place name (+ coordinates when the URL carries them)."""
    r = httpx.get(url, follow_redirects=True, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    final = str(r.url)
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(final).query)
    name = (qs.get("q") or [None])[0]
    m = re.search(r"/place/([^/]+)/@(-?\d+\.\d+),(-?\d+\.\d+)", final)
    out = {"url": url, "resolved": final, "name": name}
    if m:
        out.update(name=urllib.parse.unquote_plus(m.group(1)), lat=float(m.group(2)), lng=float(m.group(3)))
    return out
