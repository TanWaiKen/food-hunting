# Food Hunt 🍜

Turns "places people rave about on Rednote/Google" into a **verified, time-aware, walkable food
route**, then turns your trip photos into an **album** with "Proust symbols".

- Process: [docs/WORKFLOW.md](docs/WORKFLOW.md) (AI-DLC Lite: 4 stages, 2 gates)
- Every decision with Why/How/Result: [docs/DECISIONS.md](docs/DECISIONS.md)
- Look & feel: [DESIGN.md](DESIGN.md) ("Field Journal", awesome-design-md format)

## Run it locally

```powershell
uv sync
uv run foodhunt plan trips/hatyai.yaml          # gather + plan → data/hatyai/view.json, output/*.html|.notion.md
uv run uvicorn app:app --port 8000              # website: route + album + agent + remote MCP
uv run pytest -q                                # 29 tests, offline, no API key needed
```

Live: <https://food-hunting.vercel.app> · Pages: <http://localhost:8000> (all trips) · `/trip.html?trip=hatyai` (route) · `/album.html?trip=hatyai` (album) ·
`/lab.html` (design lab: three directions to compare). All times are shown in **Kuala Lumpur time (MYT)**;
set `timezone:` in the trip file (e.g. `Asia/Bangkok`) and local time appears underneath.

## How it fits together

```
                       ┌──────────────── foodhunt/tools.py ────────────────┐
                       │  ONE list of Python functions with type hints:     │
                       │  find_place · food_nearby · geocode · rednote_*    │
                       │  verify_place · crowd_forecast · walking_directions│
                       │  plan_trip_spec (TripSpec → full itinerary)        │
                       └───────┬──────────────────┬────────────────┬────────┘
            mcp.add_tool(fn)   │                  │ mcp.add_tool   │ beta_tool(fn)
                               ▼                  ▼                ▼
             Local MCP (stdio)          Remote MCP (HTTP)     Hosted agent (Claude API)
             `foodhunt-mcp`             `/mcp` on Vercel      `/api/agent` (SSE stream)
             used by Claude Code        any MCP client        Tool Runner + server-side
             on your PC (.mcp.json)     (claude.ai, others)   web_search/web_fetch
                                                               model: claude-opus-5-5
```

**How the MCP servers are made** ([foodhunt/server.py](foodhunt/server.py)): the official MCP
Python SDK (`MCPServer`) turns each function's type hints + docstring into a JSON-schema tool.
`make_server()` registers the shared functions; `mcp.run()` speaks stdio (Claude Code starts it
from `.mcp.json`), and `streamable_http_app(stateless_http=True, json_response=True)` serves the
same tools over HTTP at `/mcp` — stateless, so every request stands alone (fits serverless).

**Which agent runs?**
- *On your PC*: the agent is **Claude Code** (this app). It reads `CLAUDE`/skills/commands and calls the MCP tools. Nothing is hosted.
- *On Vercel*: there's no Claude Code, so [foodhunt/agent.py](foodhunt/agent.py) is the agent — the
  Anthropic SDK **Tool Runner** loop with our tools + Claude's server-side web search/fetch,
  model `claude-opus-5-5`, effort `high`, refusal fallback on. Your `ANTHROPIC_API_KEY` pays per use.
- The planner itself (`route.py`, `crowd.py`, `hours.py`) is plain code — deterministic, no LLM.

## Album + Travel Photo Abstraction

- Upload photos on the album page → each photo is matched to a stop by **EXIF GPS** (≤250 m),
  else by **time taken** (arrive−30 min … leave+60 min), else lands in "Unsorted" to drag.
- **Proust symbol**: 1–3 most recognisable visual facts → ≤8 flat shapes in the photo's own colours
  ([foodhunt/abstract.py](foodhunt/abstract.py)). Claude chooses facts + geometry (structured
  output); code samples colours from pixels and renders the SVG.
- Two ways to make symbols: **in Claude Code** with the skill
  [.claude/skills/travel-photo-abstraction](.claude/skills/travel-photo-abstraction/SKILL.md)
  (no API key — Claude Code is the vision model), or **"✨ Make symbol"** on the website (needs the key).
- Album layout: vertical-word cover → a scrapbook spread per day (hand-drawn route + stamped photos
  + symbols) → espresso film strip → "Proust page" memory index. Print → PDF works.

## Deploy to Vercel

1. Push this folder to GitHub (or run `npx vercel` in it). Vercel detects FastAPI from `app.py` /
   `[tool.vercel] entrypoint`, installs with uv from `pyproject.toml` + `uv.lock`, Python from `.python-version`.
2. Project → Settings → Environment Variables:

| Variable | Needed for |
|---|---|
| `ANTHROPIC_API_KEY` | the "Plan a trip" agent and "✨ Make symbol" |
| `FOODHUNT_ACCESS_TOKEN` | **set this** — protects the paid endpoints (`/api/agent`, uploads, `/mcp`) on a public URL |
| `GOOGLE_MAPS_API_KEY` | exact pins, ratings, official hours, photos (Places API New) |
| `BESTTIME_API_KEY_PRIVATE` | live crowd data instead of the estimate |

3. `vercel.json` gives the function 300 s (agent runs take 1–3 min). `public/` is served by Vercel's CDN.
4. Add the remote MCP to a client: URL `https://<your-app>.vercel.app/mcp/`, header
   `Authorization: Bearer <FOODHUNT_ACCESS_TOKEN>`.

**Known limit on Vercel:** the filesystem is read-only except `/tmp`, which is wiped between cold
starts. Bundled trips (like Hat Yai) always work; **new agent trips and uploaded album photos
don't persist there yet** — they need Vercel Blob (or another store). Locally everything persists.

## Rednote (full search)

`rednote_search` works without login (search-engine index). For full Rednote search with likes,
comments and images, run [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) yourself and
scan its QR code with your own account; `.mcp.json` already points to `http://localhost:18060/mcp`.

## Trip file cheatsheet (`trips/<city>.yaml`)

```yaml
- name: Ko Chew Stewed Pork Leg On Rice
  kind: breakfast          # breakfast | meal | hotpot | snack | dessert | mall | night_market
  hours: "06:30-14:30"     # or "Mo,Tu,Th-Su 11:00-20:00; We off" or "10:00-14:00,16:00-20:00"
  plus_code: 2F3C+4WG      # or lat/lng, address_query, or nothing (auto lookup)
  sells_out: true          # breakfast slot first, 1 h margin before close
  must: true
  not_before: "18:00"      # night markets / after-dark places
  confidence: medium       # low → red "check before going"
  order: Pork leg rice
```

## Layout

```
app.py                 Vercel entrypoint → foodhunt.web:app
foodhunt/  tools.py (shared tools) · server.py (MCP) · agent.py (hosted agent) · web.py (FastAPI)
           pipeline.py · route.py · crowd.py · hours.py · geo.py · places.py · research.py
           photos.py (album, EXIF matching) · abstract.py (Proust symbols) · render.py · config.py
public/    index.html/app.js/styles.css (route) · album.html/album.js/album.css · img/
trips/     intent files       data/<trip>/  view.json · places.json · album.json · photos/
.claude/   commands/food-hunt.md · skills/travel-photo-abstraction/ · launch.json
tests/     25 offline tests (planner, MCP over HTTP, agent wiring, album, abstraction)
```
