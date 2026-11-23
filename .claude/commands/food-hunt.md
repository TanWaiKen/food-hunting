---
description: Plan a food-hunting trip (AI-DLC Lite — Intent → Gather+Verify → Plan → Publish)
argument-hint: <city, days, where you stay, must-eats>
---

Follow docs/WORKFLOW.md exactly. Request: $ARGUMENTS

1. **INTENT** — Write `trips/<city-slug>.yaml` (copy the shape of trips/hatyai.yaml). Ask at most ONE question if
   dates or the start point are missing; otherwise assume and record the assumption in docs/DECISIONS.md.
   **Gate 1:** show the place list + assumptions and wait for "ok".
2. **GATHER + VERIFY** — For each candidate use the `foodhunt` tools: `rednote_search` (and `xiaohongshu` tools if
   that server is connected), `web_search`, `find_place`, `verify_place`, `resolve_google_share_link`.
   Rules: ≥2 independent sources per place or `confidence: low`; conflicting hours → take the overlap and
   comment the sources in the yaml; never invent coordinates — leave them empty if unsure.
3. **PLAN** — `uv run foodhunt plan trips/<slug>.yaml`. Report: stops per day, `no_coordinates`,
   `unverified_hours`. **Gate 2:** ask the user to open `output/<slug>.html`.
4. **PUBLISH** — Only after "publish": create a Notion sub-page from `output/<slug>.notion.md` under the page the
   user names (never overwrite their page). Return the link.

After every stage append Step / Decision → Why → How → Result entries to docs/DECISIONS.md.
