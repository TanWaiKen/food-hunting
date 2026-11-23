# Food Hunt — AI-DLC Lite (4 stages, 2 human gates)

The full AWS AI-DLC has about 20 stages: workspace detection, requirements, user stories,
units, functional design, NFR design, infra design, code gen, build & test, and operations.
For a one-person food-guide business, most of those produce paperwork and no extra value.
This version keeps the **3 things AI-DLC is really for**: (1) lock the intent before building,
(2) a human approves at the risky points, and (3) every decision is written down with Why/How/Result.

```
 ┌──────────┐   GATE 1   ┌──────────────────┐        ┌──────────┐   GATE 2   ┌──────────┐
 │ 1 INTENT │ ─────────▶ │ 2 GATHER+VERIFY  │ ─────▶ │ 3 PLAN   │ ─────────▶ │ 4 PUBLISH│
 └──────────┘  you OK    └──────────────────┘        └──────────┘  you OK    └──────────┘
 trips/x.yaml            data/x/places.json          output/x.html            Notion page
                         (≥2 sources / place)        output/x.notion.md       (→ WhatsApp link)
```

| # | Stage | Input → Output | Done when | Who |
|---|-------|----------------|-----------|-----|
| 1 | **Intent** | Your words → `trips/<trip>.yaml` (city, dates, start point, must-eats, pace, budget) | You say "yes, that's the trip" (**Gate 1**) | You + Claude |
| 2 | **Gather + Verify** | yaml → `data/<trip>/places.json` | Every place has coordinates, opening hours, and a source. Rednote picks are cross-checked on Google/web. Anything unverified is marked `confidence: low` | Claude + MCP tools |
| 3 | **Plan** | places → `output/<trip>.html` (map) + `output/<trip>.notion.md` | Each stop is open on arrival, avoids the peak where possible, and walking legs have turn-by-turn steps. You review the local HTML (**Gate 2**) | `foodhunt plan` (deterministic) |
| 4 | **Publish** | notion.md → Notion page (later: WhatsApp share) | Page is updated and the link works | Claude via Notion connector |

**Decision log rule:** each stage adds entries to `docs/DECISIONS.md` in the form
`Step / Decision → Why → How → Result`. If a later stage changes an earlier decision, write a new
entry; don't edit the old one.

## Using it (each new trip)

1. Tell Claude: *"/food-hunt Penang, 2 days, staying at X, must try Y"* → Claude writes `trips/penang.yaml`.
2. Claude gathers data with the `foodhunt` MCP tools (and `xiaohongshu` if it's running), then verifies.
3. `uv run foodhunt plan trips/penang.yaml` → open `output/penang.html` and check it.
4. Say "publish" → Claude pushes `output/penang.notion.md` to Notion.

The same 4 stages apply when **changing the tool itself**: write the intent (an issue or note),
let Claude gather the code context, plan and test locally, then ship.
