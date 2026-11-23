"""Render a plan to (a) local HTML with a map, (b) Notion-flavored Markdown for publishing."""
from __future__ import annotations


import json

KIND_EMOJI = {"snack": "🍣", "breakfast": "🌅", "meal": "🍛", "dessert": "🍧", "night_market": "🌙", "mall": "🛍️", "hotpot": "🍲"}
MODE = {"walking": ("🚶", "Walk"), "driving": ("🚕", "Grab")}


def _bar(by_hour: list[int], best: int | None, peak: int | None) -> str:
    """Text crowd strip 06–23h: ░ quiet ▒ medium ▓ busy, · closed."""
    s = ""
    for h in range(6, 24):
        v = by_hour[h]
        s += "·" if v == 0 else "░" if v < 35 else "▒" if v < 70 else "▓"
    return s


def _img(p: dict) -> list[str]:
    return [i for i in (p.get("notion_images") or []) + (p.get("images") or []) if i]


# ---------------- Notion ----------------

def notion_md(trip: dict, days: list[dict], leftover: list[dict], no_loc: list[dict] = ()) -> str:
    from . import tz

    sh = tz.shift_minutes(trip.get("timezone"), days[0]["date"] if days else None)
    K = lambda t: tz.shift_text(t, sh)  # noqa: E731 — local → MYT
    lbl = tz.DISPLAY_LABEL
    L: list[str] = []
    L.append(f"<callout icon=\"🧭\" color=\"blue_bg\">\n<b>How to use:</b> follow Day 1 top to bottom. Each stop shows when to arrive, "
             f"why that time, and how to walk there. Tap <b>Open full-day route</b> for Google Maps navigation.\\\n"
             f"Start: <b>{trip['start']['name']}</b> · All times are Kuala Lumpur time ({lbl})"
             + (f", {abs(sh) // 60} h {'ahead of' if sh > 0 else 'behind'} local time" if sh else "")
             + " · Crowd: ░ quiet ▒ medium ▓ busy · closed\n</callout>")
    L.append("<p />")
    for i, d in enumerate(days, 1):
        if not d["stops"]:
            continue
        L.append(f"## Day {i} — {d['weekday']} {d['date']}")
        L.append(f"[🗺️ Open full-day route in Google Maps]({d['map_link']})")
        L.append("")
        for n, s in enumerate(d["stops"], 1):
            p, leg, c = s["place"], s["leg"], s["crowd"]
            em, verb = MODE[leg["mode"]]
            dist = f"{leg['meters']} m · " if leg.get("meters") else ""
            frm = "start" if n == 1 else f"stop {n - 1}"
            steps = "\n".join(f"{k}. {st}" for k, st in enumerate(leg["steps"], 1)) or "Use the Google Maps link."
            L.append(f"<toggle>\n{em} {verb} from {frm}: {dist}{leg['minutes']} min\n\n{steps}\n</toggle>")
            L.append("")
            title = p.get("display") or p["name"]
            L.append(f"### {n}. {KIND_EMOJI.get(p.get('kind'), '🍽️')} {title}")
            L.append(f"<span color=\"gray\">{s.get('slot', '')}</span>")
            meta = []
            if p.get("rating"):
                meta.append(f"⭐ {p['rating']}" + (f" ({p['reviews']:,} reviews)" if p.get("reviews") else ""))
            meta.append(f"🕒 Arrive <b>{K(s['arrive'])} {lbl}</b> → leave {K(s['leave'])}" + (f" (local {s['arrive']})" if sh else ""))
            meta.append(f"Open today: {K(s['hours_today'])}")
            L.append(" · ".join(meta))
            L.append("")
            crowd_src = "estimated" if c["source"] == "estimate" else "live data"
            why = [f"Quietest {K(c['best'] or '')} · Busiest {K(c['peak'] or '')} ({crowd_src})"]
            if s["wait_min"] > 10 and s.get("wait_reason") == "opening":
                why.append(f"opens at {K(s['arrive'])} — arrive on the dot")
            elif s["wait_min"] > 30:
                why.append(f"{s['wait_min'] // 60} h {s['wait_min'] % 60} min free time before this — rest / shop")
            if p.get("sells_out"):
                why.append("sells out early")
            L.append(f"<callout icon=\"⏰\" color=\"{'red_bg' if s['crowd_now'] >= 70 else 'yellow_bg' if s['crowd_now'] >= 35 else 'green_bg'}\">\n"
                     f"Crowd at {K(s['arrive'])}: <b>{_level(s['crowd_now'])}</b> `{_bar(c['by_hour'], c.get('best_hour'), c.get('peak_hour'))}`\\\n"
                     f"{' · '.join(why)}\n</callout>")
            if p.get("order"):
                L.append(f"🍴 <b>Order:</b> {p['order']}")
            if p.get("tip"):
                L.append(f"💡 {p['tip']}")
            if not s["hours_known"] or p.get("confidence") == "low":
                L.append("<span color=\"red\">⚠️ Hours not verified — check Google Maps before going.</span>")
            if p.get("location") == "approx" or p.get("coord_source") == "street address (approx.)":
                L.append("<span color=\"orange\">📍 Pin is street-level — use the Google Maps link for the exact door.</span>")
            L.append((f"📍 {p['address']} · " if p.get("address") else "📍 ") + f"[Google Maps]({p.get('maps_url')})" +(f" · [Rednote]({p['rednote']})" if p.get("rednote") else ""))
            imgs = _img(p)
            if len(imgs) >= 2:
                cols = "\n".join(f"<column ratio=\"{100 // min(3, len(imgs))}\">\n{_image_tag(x)}\n</column>" for x in imgs[:3])
                L.append(f"<columns>\n{cols}\n</columns>")
            elif imgs:
                L.append(_image_tag(imgs[0]))
            L.append("")
        L.append("---")
    if leftover:
        L.append("## Didn't fit (closed on these days or too many stops)")
        L.append("\n".join(f"- <b>{p.get('display') or p['name']}</b> — {p.get('hours') or 'hours unknown'} · [Google Maps]({p.get('maps_url')})" for p in leftover))
    if no_loc:
        L.append("## 📍 Need exact location (not routed yet)")
        L.append("On your list, but no free map source has them. Tap the link — or add a Google Maps API key and re-run, and they'll be routed automatically.")
        L.append("\n".join(f"- <b>{p.get('display') or p['name']}</b> — [Google Maps]({p.get('maps_url')})" for p in no_loc))
    return "\n\n".join(x for x in L if x.strip())  # Notion needs a blank line between blocks


def _image_tag(src: str) -> str:
    return f"<image source=\"{src}\" />" if src.startswith("notion-file-block://") else f"![]({src})"


def _level(v: int) -> str:
    return "quiet" if v < 35 else "medium" if v < 70 else "busy"


# ---------------- web view model (one JSON the UI, API and exports share) ----------------

_PLACE_KEYS = ("name", "display", "kind", "rating", "reviews", "order", "tip", "address", "maps_url",
               "lat", "lng", "confidence", "location", "coord_source", "sells_out", "must", "hours", "share_link")


def _web_images(p: dict) -> list[str]:
    """notion-file-block refs → local copies in public/img (if downloaded); keep http(s) URLs."""
    from .config import PUBLIC_DIR

    out = []
    for src in _img(p):
        if src.startswith("notion-file-block://"):
            uuid = src.split("/")[3].split("?")[0]
            if (PUBLIC_DIR / "img" / f"{uuid}.jpg").exists():
                out.append(f"img/{uuid}.jpg")
        elif src.startswith("http"):
            out.append(src)
    return out


def _place_view(p: dict) -> dict:
    v = {k: p.get(k) for k in _PLACE_KEYS if p.get(k) is not None}
    v["display"] = p.get("display") or p["name"]
    v["images"] = _web_images(p)
    v["approx"] = p.get("location") == "approx" or p.get("coord_source") == "street address (approx.)"
    return v


def view_model(trip: dict, days: list[dict], leftover: list[dict], no_loc: list[dict] = (), *, crowd_source: str = "estimate",
               place_source: str = "openstreetmap") -> dict:
    from . import tz

    sh = tz.shift_minutes(trip.get("timezone"), days[0]["date"] if days else None)
    K = lambda t: tz.shift_text(t, sh) if t else t  # noqa: E731 — local → MYT
    out_days = []
    for d in days:
        stops = []
        for s in d["stops"]:
            leg = s["leg"]
            c = s["crowd"]
            stops.append({
                # what people read is MYT; *_local is the destination clock (photo matching, signage)
                "slot": s.get("slot"), "arrive": K(s["arrive"]), "leave": K(s["leave"]),
                "arrive_local": s["arrive"], "leave_local": s["leave"],
                "wait_min": s["wait_min"], "wait_reason": s.get("wait_reason"),
                "hours_today": K(s["hours_today"]), "hours_local": s["hours_today"], "hours_known": s["hours_known"],
                "crowd_now": s["crowd_now"],
                "crowd": {"best": K(c.get("best")), "peak": K(c.get("peak")), "best_hour": c.get("best_hour"),
                          "peak_hour": c.get("peak_hour"), "by_hour": c.get("by_hour"), "source": c.get("source")},
                "leg": {"mode": leg["mode"], "meters": leg.get("meters"), "minutes": leg["minutes"],
                        "steps": leg.get("steps", []), "source": leg.get("source"),
                        "geometry": [[round(y, 6), round(x, 6)] for x, y in (leg.get("geometry") or [])]},  # [lat,lng]
                "place": _place_view(s["place"]),
            })
        out_days.append({"date": d["date"], "weekday": d["weekday"], "map_link": d["map_link"], "stops": stops,
                         "walk_m": sum(s["leg"]["meters"] or 0 for s in stops if s["leg"]["mode"] == "walking")})
    return {
        "trip": {"title": trip["trip"], "city": trip["city"], "start": trip["start"],
                 "generated_at": tz.now_display(),
                 "time": {"display": tz.DISPLAY_TZ, "label": tz.DISPLAY_LABEL, "local": trip.get("timezone") or tz.DISPLAY_TZ,
                          "shift_min": sh},
                 "sources": {"crowd": crowd_source, "places": place_source}},
        "days": out_days,
        "leftover": [_place_view(p) for p in leftover],
        "no_location": [_place_view(p) for p in no_loc],
    }


def export_html(view: dict, img_base: str = "../public/") -> str:
    """Self-contained copy of the web UI (data + CSS + JS inlined) for offline sharing."""
    import json

    from .config import PUBLIC_DIR

    page = (PUBLIC_DIR / "trip.html").read_text(encoding="utf-8")
    css = (PUBLIC_DIR / "styles.css").read_text(encoding="utf-8")
    js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
    data = json.dumps(view, ensure_ascii=False).replace("</", "<\\u002f")  # never close the <script> early
    page = page.replace('<link rel="stylesheet" href="styles.css">', f"<style>{css}</style>")
    page = page.replace('<script src="app.js"></script>',
                        f"<script>window.__TRIP__={data};window.__IMG_BASE__={json.dumps(img_base)};</script><script>{js}</script>")
    return page
