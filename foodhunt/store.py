"""Storage for everything the app writes: trips, albums and photos.

Two backends, same keys ("<slug>/view.json", "<slug>/album.json", "<slug>/photos/<id>.jpg"):

- Local disk (default; your PC): files under DATA_DIR (= the project's data/ folder).
- Vercel Blob (when BLOB_READ_WRITE_TOKEN is set — Vercel adds it when you connect a Blob store
  to the project): permanent, survives cold starts. Free on Hobby: 1 GB, 10k reads, 2k writes/month.

Reads always fall back to the files bundled with the deploy (BUNDLED_DATA), so the Hat Yai sample
trip and album work before anything was ever uploaded. The first write to an album copies the
bundled album into Blob (album.json only — the bundled photos keep being served from the deploy).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

from .config import BUNDLED_DATA, DATA_DIR

ACCESS = os.getenv("FOODHUNT_BLOB_ACCESS", "public")   # must match the store's mode (chosen when it's created)
_INDEX = "index.json"                                   # list of trip slugs that live in Blob
_url_cache: dict[str, tuple[float, str]] = {}           # key → (expires, CDN url)


def on_blob() -> bool:
    return bool(os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv("VERCEL_BLOB_READ_WRITE_TOKEN"))


def backend() -> str:
    return "vercel-blob" if on_blob() else "local-disk"


def _blob():
    from vercel.blob import sync  # imported lazily: local runs never need it
    return sync


# ---------------- bytes ----------------

def read_bytes(key: str) -> bytes | None:
    """Fresh read (writes are visible immediately, not after the CDN's ~60 s)."""
    if on_blob():
        b = _blob()
        try:
            if ACCESS == "private":
                return b.get_blob(key, access="private").body
            h = b.head_blob(key)                      # API call → current etag
            r = httpx.get(h.url, params={"v": h.etag.strip('"')}, timeout=20)  # etag busts stale CDN copies
            r.raise_for_status()
            return r.content
        except b.BlobNotFoundError:
            pass
    else:
        f = DATA_DIR / key
        if f.exists():
            return f.read_bytes()
    f = BUNDLED_DATA / key
    return f.read_bytes() if f.exists() else None


def write_bytes(key: str, data: bytes, content_type: str) -> None:
    if on_blob():
        res = _blob().put_blob(key, data, access=ACCESS, content_type=content_type,
                               allow_overwrite=True, cache_control_max_age=60 if key.endswith(".json") else 31536000)
        _url_cache[key] = (time.time() + 3600, res.url)
        return
    f = DATA_DIR / key
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)


def exists(key: str) -> bool:
    if on_blob():
        b = _blob()
        try:
            b.head_blob(key)
            return True
        except b.BlobNotFoundError:
            pass
    elif (DATA_DIR / key).exists():
        return True
    return (BUNDLED_DATA / key).exists()


def locate(key: str) -> tuple[str, str | Path] | None:
    """Where to serve a file from: ("url", public CDN url) | ("path", local file) | ("bytes", None) | None."""
    if on_blob():
        hit = _url_cache.get(key)
        if hit and hit[0] > time.time():
            return ("url", hit[1]) if ACCESS == "public" else ("bytes", None)
        b = _blob()
        try:
            h = b.head_blob(key)
            _url_cache[key] = (time.time() + 3600, h.url)
            return ("url", h.url) if ACCESS == "public" else ("bytes", None)
        except b.BlobNotFoundError:
            pass
    elif (DATA_DIR / key).exists():
        return ("path", DATA_DIR / key)
    f = BUNDLED_DATA / key
    return ("path", f) if f.exists() else None


# ---------------- JSON ----------------

def read_json(key: str):
    raw = read_bytes(key)
    return json.loads(raw) if raw is not None else None


def write_json(key: str, obj) -> None:
    write_bytes(key, json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8"), "application/json")


# ---------------- trips ----------------

def trip_slugs() -> set[str]:
    """Every trip that has a view.json: bundled + written (local folder or Blob index)."""
    slugs = {p.parent.name for p in BUNDLED_DATA.glob("*/view.json")} if BUNDLED_DATA.exists() else set()
    if on_blob():
        slugs |= set(read_json(_INDEX) or [])
    elif DATA_DIR.exists():
        slugs |= {p.parent.name for p in DATA_DIR.glob("*/view.json")}
    return slugs


def save_trip(slug: str, view: dict) -> None:
    write_json(f"{slug}/view.json", view)
    if on_blob():
        idx = set(read_json(_INDEX) or [])
        if slug not in idx:
            write_json(_INDEX, sorted(idx | {slug}))


def load_trip(slug: str) -> dict | None:
    return read_json(f"{slug}/view.json")


# ---------------- media sync (PC → Blob) ----------------

def push_media(public_img: Path, data_dir: Path) -> dict:
    """Copy photos that only live on this PC (they're kept off GitHub) into Blob:
    public/img/*.jpg → "img/<name>", data/<slug>/photos/*.jpg → "<slug>/photos/<name>".
    Skips files already in Blob, so it is safe to run again after adding photos."""
    if not on_blob():
        raise SystemExit("Set BLOB_READ_WRITE_TOKEN first (it's in .env.local after `vercel env pull`).")
    files = [(f"img/{f.name}", f) for f in sorted(public_img.glob("*.jpg"))]
    files += [(f"{f.parent.parent.name}/photos/{f.name}", f) for f in sorted(data_dir.glob("*/photos/*.jpg"))]
    done = {"uploaded": 0, "skipped": 0}
    for key, f in files:
        where = locate(key)
        if where and where[0] == "url":
            done["skipped"] += 1
            continue
        write_bytes(key, f.read_bytes(), "image/jpeg")
        done["uploaded"] += 1
    return done


if __name__ == "__main__":  # uv run python -m foodhunt.store push-media
    import sys

    from .config import PUBLIC_DIR
    if sys.argv[1:] == ["push-media"]:
        print(push_media(PUBLIC_DIR / "img", BUNDLED_DATA))
    else:
        print("usage: python -m foodhunt.store push-media")
