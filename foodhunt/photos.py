"""Album photos: store, read EXIF (GPS + time), match each photo to a stop of the trip.

Matching order (first that works wins, and is recorded so the UI can show *why*):
  1. GPS  — nearest routed stop within 250 m of where the photo was taken
  2. time — taken on a trip day between (arrive − 30 min) and (leave + 60 min) of a stop
  3. none — "unsorted"; the user drags it onto a place (PATCH)
Storage: <DATA_DIR>/<slug>/photos/*.jpg + album.json. Locally that is the project folder;
on Vercel /tmp is NOT permanent — use Vercel Blob for albums there (see README).
"""
from __future__ import annotations

import datetime as dt
import io
import json
import uuid
from pathlib import Path

import shutil

from . import geo
from .config import BUNDLED_DATA, DATA_DIR

MAX_PX = 1600
GPS_RADIUS_M = 250


def album_dir(slug: str) -> Path:
    """Writable album folder. On Vercel (DATA_DIR=/tmp) the first access copies the album that
    shipped with the deployment, so bundled albums show up and new uploads can be added on top."""
    d = DATA_DIR / slug
    src = BUNDLED_DATA / slug
    if d != src and not (d / "album.json").exists() and (src / "album.json").exists():
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / "album.json", d / "album.json")
        if (src / "photos").exists():
            shutil.copytree(src / "photos", d / "photos", dirs_exist_ok=True)
    return d


def load_album(slug: str) -> dict:
    f = album_dir(slug) / "album.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"photos": []}


def save_album(slug: str, album: dict) -> None:
    album_dir(slug).mkdir(parents=True, exist_ok=True)
    (album_dir(slug) / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------- EXIF ----------------

def _ratio(v) -> float:
    try:
        return float(v)
    except TypeError:
        return v[0] / v[1]


def read_exif(im) -> dict:
    """{'lat','lng','taken_at'} from a PIL image (any may be missing)."""
    out: dict = {}
    try:
        ex = im.getexif()
    except Exception:  # noqa: BLE001
        return out
    when = ex.get_ifd(0x8769).get(36867) or ex.get(306)  # DateTimeOriginal, else DateTime
    if when:
        try:
            out["taken_at"] = dt.datetime.strptime(str(when).strip("\x00 "), "%Y:%m:%d %H:%M:%S").isoformat()
        except ValueError:
            pass
    gps = ex.get_ifd(0x8825)
    if gps and 2 in gps and 4 in gps:
        def deg(t):
            d, m, s = (_ratio(x) for x in t)
            return d + m / 60 + s / 3600
        lat, lng = deg(gps[2]), deg(gps[4])
        if gps.get(1) in ("S", b"S"):
            lat = -lat
        if gps.get(3) in ("W", b"W"):
            lng = -lng
        out["lat"], out["lng"] = round(lat, 6), round(lng, 6)
    return out


# ---------------- matching ----------------

def stop_index(view: dict) -> list[dict]:
    """Flatten the itinerary into matchable stops (+ unrouted places, GPS-only)."""
    out = []
    for i, d in enumerate(view["days"]):
        for j, s in enumerate(d["stops"]):
            p = s["place"]
            out.append({"key": f"{i}-{j}", "name": p["display"], "place": p["name"], "lat": p["lat"], "lng": p["lng"],
                        # EXIF time is the phone's local clock abroad → match on local, not MYT
                        "date": d["date"], "arrive": s.get("arrive_local", s["arrive"]), "leave": s.get("leave_local", s["leave"])})
    for k, p in enumerate(view.get("no_location", []) + view.get("leftover", [])):
        out.append({"key": f"x-{k}", "name": p["display"], "place": p["name"], "lat": p.get("lat"), "lng": p.get("lng")})
    return out


def match(meta: dict, stops: list[dict]) -> dict:
    if meta.get("lat") is not None:
        cands = [(geo.haversine_m((meta["lat"], meta["lng"]), (s["lat"], s["lng"])), s)
                 for s in stops if s.get("lat") is not None]
        if cands:
            d, s = min(cands, key=lambda c: c[0])
            if d <= GPS_RADIUS_M:
                return {"stop_key": s["key"], "by": "gps", "distance_m": round(d)}
    if meta.get("taken_at"):
        t = dt.datetime.fromisoformat(meta["taken_at"])
        for s in stops:
            if s.get("date") != t.date().isoformat():
                continue
            a = _mins(s["arrive"]) - 30
            b = _mins(s["leave"]) + 60
            if a <= t.hour * 60 + t.minute <= b:
                return {"stop_key": s["key"], "by": "time"}
    return {"stop_key": None, "by": None}


def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


# ---------------- ingest ----------------

def add_photo(slug: str, view: dict, data: bytes, filename: str = "", stop_key: str | None = None) -> dict:
    """Save one upload (EXIF-rotated, ≤1600px JPEG), read metadata, auto-match, record in album.json."""
    from PIL import Image, ImageOps

    im = Image.open(io.BytesIO(data))
    meta = read_exif(im)                       # read before transpose drops EXIF
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((MAX_PX, MAX_PX))
    pid = uuid.uuid4().hex[:12]
    folder = album_dir(slug) / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
    (folder / f"{pid}.jpg").write_bytes(buf.getvalue())

    m = {"stop_key": stop_key, "by": "manual"} if stop_key else match(meta, stop_index(view))
    from .abstract import palette

    photo = {"id": pid, "src": f"api/trips/{slug}/photos/{pid}.jpg", "file": filename, "w": im.width, "h": im.height,
             **meta, **m, "palette": palette(buf.getvalue()), "symbol": None}
    album = load_album(slug)
    album["photos"].append(photo)
    save_album(slug, album)
    return photo


def update_photo(slug: str, pid: str, **changes) -> dict:
    album = load_album(slug)
    for p in album["photos"]:
        if p["id"] == pid:
            p.update(changes)
            save_album(slug, album)
            return p
    raise KeyError(pid)


def photo_path(slug: str, pid: str) -> Path:
    return album_dir(slug) / "photos" / f"{pid}.jpg"


def seed_from_trip(slug: str, trip: dict, view: dict, img_dir: Path) -> int:
    """Put the photos already in the trip file (notion_images, downloaded to public/img) into the album."""
    by_name = {s["place"]: s["key"] for s in stop_index(view)}
    have = {p.get("file") for p in load_album(slug)["photos"]}
    n = 0
    for place in trip["places"]:
        for ref in place.get("notion_images") or []:
            uuid_ = ref.split("/")[3].split("?")[0]
            f = img_dir / f"{uuid_}.jpg"
            if f.exists() and f.name not in have and place["name"] in by_name:
                add_photo(slug, view, f.read_bytes(), f.name, stop_key=by_name[place["name"]])
                n += 1
    return n
