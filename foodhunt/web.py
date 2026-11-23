"""FastAPI app — the one thing Vercel runs.

  GET  /                    trip UI (public/index.html)
  GET  /api/health          what's configured (keys present? agent enabled?)
  GET  /api/trips           list trips;   GET /api/trips/{slug} → view JSON
  POST /api/agent           {"prompt": "..."} → Server-Sent Events from the hosted Claude agent
  POST /api/plan            TripSpec JSON → plan without the agent (deterministic)
  /mcp                      remote MCP server (streamable HTTP, stateless) with the same tools

Run locally:  uv run uvicorn foodhunt.web:app --reload --port 8000
"""
from __future__ import annotations

import contextlib
import hmac
import json
import os

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from starlette.types import ASGIApp, Receive, Scope, Send

from . import abstract, agent, crowd, geo, photos, pipeline
from .config import ACCESS_TOKEN, AGENT_MODEL, BUNDLED_DATA, DATA_DIR, ON_VERCEL, PUBLIC_DIR, find_trip_file
from .server import make_server
from .tools import TripSpec

# ---- remote MCP (stateless + JSON responses: each request stands alone, fits serverless) ----
mcp_server = make_server(remote=True)
mcp_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
    # Vercel serves on your own domain; Host-header checks would reject it. Auth is the bearer token below.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    # a mounted Starlette app's lifespan doesn't run by itself — start the MCP session manager here
    async with mcp_app.router.lifespan_context(mcp_app):
        yield


app = FastAPI(title="Food Hunt", lifespan=lifespan)


def _check(token: str | None) -> None:
    if ACCESS_TOKEN and not (token and hmac.compare_digest(token, ACCESS_TOKEN)):
        raise HTTPException(401, "Access code required")


def require_token(authorization: str | None = Header(default=None)) -> None:
    _check(authorization.removeprefix("Bearer ").strip() if authorization else None)


class BearerGate:
    """Protects /mcp with the same access code (Authorization: Bearer <code>)."""

    def __init__(self, inner: ASGIApp):
        self.inner = inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and ACCESS_TOKEN:
            auth = dict(scope["headers"]).get(b"authorization", b"").decode()
            if not hmac.compare_digest(auth.removeprefix("Bearer ").strip(), ACCESS_TOKEN):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"error":"Access code required"}'})
                return
        await self.inner(scope, receive, send)


app.mount("/mcp", BearerGate(mcp_app))


# ---------------- API ----------------

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "agent": bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")),
        "model": AGENT_MODEL,
        "access_code_required": bool(ACCESS_TOKEN),
        "google_places": geo.has_google(),
        "besttime": crowd.has_besttime(),
    }


@app.get("/api/trips")
def list_trips():
    slugs = set()
    for d in (BUNDLED_DATA, DATA_DIR):
        if d.exists():
            slugs |= {p.parent.name for p in d.glob("*/view.json")}
    out = []
    for s in sorted(slugs):
        v = json.loads(find_trip_file(s).read_text(encoding="utf-8"))
        stops = [st for d in v["days"] for st in d["stops"]]
        album = photos.load_album(s)["photos"]
        arrive = {f"{i}-{j}": st["arrive"] for i, d in enumerate(v["days"]) for j, st in enumerate(d["stops"])}
        # cover: an evening photo if there is one (lights, night market), else any routed photo
        routed = [p for p in album if p.get("stop_key") in arrive]
        night = sorted((p for p in routed if arrive[p["stop_key"]] >= "18:00"), key=lambda p: arrive[p["stop_key"]], reverse=True)
        cover = (night or routed or [{}])[0].get("src") \
            or next((st["place"]["images"][0] for st in stops if st["place"].get("images")), None)
        symbols = [abstract.render_svg(abstract.SymbolSpec.model_validate(p["symbol"]), p["palette"], 64)
                   for p in album if p.get("symbol")][:5]
        out.append({"slug": s, "title": v["trip"]["title"], "city": v["trip"]["city"], "days": len(v["days"]),
                    "stops": len(stops), "first_day": v["days"][0]["date"] if v["days"] else None,
                    "last_day": v["days"][-1]["date"] if v["days"] else None,
                    "walk_m": sum(d.get("walk_m", 0) for d in v["days"]),
                    "photos": len(album), "cover": cover, "symbols": symbols,
                    # for the home-page search: places and what to order there
                    "places": [st["place"]["display"] for st in stops],
                    "dishes": [st["place"]["order"] for st in stops if st["place"].get("order")]})
    return out


@app.get("/api/trips/{slug}")
def get_trip(slug: str):
    f = find_trip_file(pipeline.slugify(slug))
    if not f:
        raise HTTPException(404, "Trip not found")
    return json.loads(f.read_text(encoding="utf-8"))


class AgentRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)


@app.post("/api/agent", dependencies=[Depends(require_token)])
def run_agent(req: AgentRequest):
    def sse():
        for ev in agent.run(req.prompt):
            yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/plan", dependencies=[Depends(require_token)])
def plan(spec: TripSpec):
    res = pipeline.build(spec.model_dump(), pipeline.slugify(spec.trip))
    return res


# ---------------- album ----------------

def _view(slug: str) -> dict:
    f = find_trip_file(slug)
    if not f:
        raise HTTPException(404, "Trip not found")
    return json.loads(f.read_text(encoding="utf-8"))


@app.get("/api/trips/{slug}/album")
def get_album(slug: str):
    view = _view(slug)
    album = photos.load_album(slug)
    for p in album["photos"]:
        if p.get("symbol"):
            p["symbol_svg"] = abstract.render_svg(abstract.SymbolSpec.model_validate(p["symbol"]), p["palette"])
    return {"view": view, "album": album, "stops": photos.stop_index(view)}


@app.post("/api/trips/{slug}/photos", dependencies=[Depends(require_token)])
async def upload_photos(slug: str, files: list[UploadFile] = File(...), stop_key: str | None = Form(None)):
    """Upload photos. With stop_key (from a restaurant card) they go straight to that stop;
    without it they're matched by EXIF GPS/time."""
    view = _view(slug)
    if stop_key and stop_key not in {s["key"] for s in photos.stop_index(view)}:
        raise HTTPException(400, "Unknown stop")
    added = []
    for f in files[:40]:
        data = await f.read()
        if len(data) > 25_000_000:
            raise HTTPException(413, f"{f.filename} is over 25 MB")
        try:
            added.append(photos.add_photo(slug, view, data, f.filename or "", stop_key=stop_key or None))
        except Exception as e:  # noqa: BLE001 — a non-image shouldn't kill the batch
            added.append({"file": f.filename, "error": str(e)[:200]})
    return {"added": added}


@app.get("/api/trips/{slug}/photos/{pid}.jpg")
def photo_file(slug: str, pid: str):
    f = photos.photo_path(pipeline.slugify(slug), pipeline.slugify(pid))
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


class PhotoPatch(BaseModel):
    stop_key: str | None = None
    caption: str | None = Field(None, max_length=80)
    symbol: abstract.SymbolSpec | None = None


@app.patch("/api/trips/{slug}/photos/{pid}", dependencies=[Depends(require_token)])
def patch_photo(slug: str, pid: str, body: PhotoPatch):
    changes = body.model_dump(exclude_unset=True)
    if "stop_key" in changes:
        changes["by"] = "manual"
    if changes.get("symbol"):
        changes["symbol"] = body.symbol.model_dump()
    try:
        return photos.update_photo(slug, pid, **changes)
    except KeyError:
        raise HTTPException(404, "Photo not found") from None


@app.post("/api/trips/{slug}/photos/{pid}/abstract", dependencies=[Depends(require_token)])
def abstract_photo(slug: str, pid: str):
    f = photos.photo_path(slug, pid)
    if not f.exists():
        raise HTTPException(404, "Photo not found")
    p = next(x for x in photos.load_album(slug)["photos"] if x["id"] == pid)
    stop = next((s for s in photos.stop_index(_view(slug)) if s["key"] == p.get("stop_key")), None)
    ctx = f"Taken at {stop['name']}" + (f", around {stop['arrive']}" if stop and stop.get("arrive") else "") if stop else ""
    try:
        spec = abstract.extract_spec(f.read_bytes(), context=ctx)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Abstraction failed: {e}") from e
    p = photos.update_photo(slug, pid, symbol=spec.model_dump())
    return {**p, "symbol_svg": abstract.render_svg(spec, p["palette"])}


# ---------------- UI (Vercel's CDN serves public/ directly; this is for local runs) ----------------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(PUBLIC_DIR / "index.html")


if not ON_VERCEL:  # on Vercel, public/ is served by the CDN — Vercel says not to mount it
    app.mount("/", StaticFiles(directory=PUBLIC_DIR), name="public")
