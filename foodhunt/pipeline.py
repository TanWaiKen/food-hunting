"""Stage 2 (gather) + Stage 3 (plan).

CLI:   uv run foodhunt plan trips/hatyai.yaml
Code:  build(trip_dict, slug)  — used by the MCP tool and the hosted agent (no files needed)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from . import crowd, geo, places, render, route
from . import store
from .config import DATA_DIR, OUTPUT_DIR


def load_trip(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "trip"


def enrich(trip: dict, slug: str, refresh: bool = False, log=lambda m: print(m, file=sys.stderr)) -> list[dict]:
    """Fill coordinates/hours/rating for each place. Cached in <DATA_DIR>/<slug>/places.json."""
    cache_file = DATA_DIR / slug / "places.json"
    cache = {} if refresh or not cache_file.exists() else {p["name"]: p for p in json.loads(cache_file.read_text(encoding="utf-8"))}
    center = tuple(trip["center"])
    out = []
    for p in trip["places"]:
        p = dict(p)
        if p["name"] in cache and not refresh:
            p = {**cache[p["name"]], **p}  # trip file always wins over looked-up data
        if p.get("lat") is None and p.get("plus_code"):
            ll = geo.decode_plus_code(p["plus_code"], center)
            if ll:
                p["lat"], p["lng"] = ll
                p.setdefault("coord_source", "plus_code")
        if p.get("lat") is None or (geo.has_google() and not p.get("place_id")):
            try:
                found = places.lookup(p.get("search") or p["name"], trip["city"], near=center)
            except Exception as e:  # noqa: BLE001 — one bad lookup must not kill the trip
                found = None
                log(f"  ! lookup failed for {p['name']}: {e}")
            if found:
                for k, v in found.items():
                    if v is not None and p.get(k) is None:
                        p[k] = v
                p.setdefault("coord_source", found.get("source"))
            if p.get("lat") is None and p.get("address_query"):
                g = geo.geocode_osm(f"{p['address_query']}, {trip['city']}")
                if g:
                    p["lat"], p["lng"] = g["lat"], g["lng"]
                    p["coord_source"] = "street address (approx.)"
            # >15 km from the centre is almost certainly a wrong match
            if p.get("lat") is not None and geo.haversine_m(center, (p["lat"], p["lng"])) > 15000:
                log(f"  ! {p['name']}: match is far from city centre, ignoring coordinates")
                p["lat"] = p["lng"] = None
        if p.get("share_link"):
            p.setdefault("maps_url", p["share_link"])  # exact Google place the user picked
        p.setdefault("maps_url", geo.gmaps_place_link(f"{p.get('search') or p['name']} {trip['city']}", p.get("place_id")))
        if geo.has_google() and p.get("photos") and not p.get("images"):
            p["images"] = [u for u in (places.google_photo_uri(ph) for ph in p["photos"][:2]) if u]
        out.append(p)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def build(trip: dict, slug: str, refresh: bool = False, offline: bool = False, write: bool = True) -> dict:
    """Gather + plan + render. Returns {"view": <UI JSON>, "summary": <short text-friendly dict>}."""
    ps = enrich(trip, slug, refresh)
    for p in ps:
        p["_hours"] = places.parse_hours(p)
    no_loc = [p for p in ps if p.get("lat") is None]
    days, leftover = route.plan(trip, ps, fetch_routes=not offline)
    view = render.view_model(
        trip, days, leftover, no_loc,
        crowd_source="besttime" if crowd.has_besttime() else "estimate",
        place_source="google_places" if geo.has_google() else "openstreetmap",
    )
    if write:
        store.save_trip(slug, view)                     # data/<slug>/view.json, or Vercel Blob
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / f"{slug}.notion.md").write_text(render.notion_md(trip, days, leftover, no_loc), encoding="utf-8")
        (OUTPUT_DIR / f"{slug}.html").write_text(render.export_html(view), encoding="utf-8")
    from . import tz

    sh = view["trip"]["time"]["shift_min"]
    summary = {
        "slug": slug,
        "times": f"{tz.DISPLAY_LABEL} (Kuala Lumpur)",
        "days": [{"date": d["date"], "stops": [f"{tz.shift_hhmm(s['arrive'], sh)} {s['place']['name']} ({s['leg']['mode']} {s['leg']['minutes']}m)"
                                               for s in d["stops"]]} for d in days],
        "did_not_fit": [p["name"] for p in leftover],
        "no_coordinates": [p["name"] for p in no_loc],
        "unverified_hours": [p["name"] for p in ps if p["_hours"] is None],
    }
    return {"view": view, "summary": summary}


def run(trip_path: str, refresh: bool = False, offline: bool = False) -> dict:
    slug = Path(trip_path).stem
    res = build(load_trip(trip_path), slug, refresh, offline)
    return {"html": str(OUTPUT_DIR / f"{slug}.html"), "notion_md": str(OUTPUT_DIR / f"{slug}.notion.md"), **res["summary"]}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="foodhunt")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan", help="gather + plan + render a trip file")
    pl.add_argument("trip")
    pl.add_argument("--refresh", action="store_true", help="ignore cached lookups")
    pl.add_argument("--offline", action="store_true", help="skip turn-by-turn routing calls")
    a = ap.parse_args()
    if a.cmd == "plan":
        print(json.dumps(run(a.trip, a.refresh, a.offline), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
