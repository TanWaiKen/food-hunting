---
name: travel-photo-abstraction
description: Travel Photo Abstraction ("image Proust effect") — turn trip photos into minimal abstract symbols made of the photo's most recognisable visual facts and its own colours, then compose photo + symbol for the album. Use when the user uploads/points to travel or food photos and wants symbols, a memory index, a diptych, or the Food Hunt album filled in. 旅行照片抽象 / 普鲁斯特效应 / 相册符号.
---

# Travel Photo Abstraction

A smell can bring back a whole afternoon. This skill does that for photos: keep the 1–3 things
your eye actually remembers, redraw them as a few flat shapes in the photo's own colours.
Design rules: `DESIGN.md` §10. Code: `foodhunt/abstract.py` (schema, palette, renderer).

## Inputs
- Photos: files the user gives, or photos already in a trip album
  (`data/<trip>/album.json` + `data/<trip>/photos/<id>.jpg`).
- Optional context per photo: the place and time it was taken (from the album's `stop_key`).

## Procedure (per photo)

1. **Look** at the photo (Read the image file). Write down what is *specifically* there.
2. **Pick 1–3 visual facts** — the most recognisable, concrete things: "red plastic stool",
   "steam over the pork leg", "fairy lights in the branches". Never generic ("food", "restaurant").
   Never text, logos or faces.
3. **Get the palette from pixels** — don't guess colours:
   `uv run python -m foodhunt.abstract palette <photo.jpg>` → 5 hex colours, index 0 = most dominant,
   4 = lightest (normally the background).
4. **Draw** a `SymbolSpec` (JSON) on a 100×100 grid with ≤ 8 shapes from:
   `circle ring rect line arc(bowl) triangle wave dots(row) steam`.
   Each shape: `x y w h rotate color(0-4) fill opacity count`. Sparse, balanced, room to breathe.
   Map facts to shapes literally: bowl → `arc`/`ring`; lights/seeds/stools → `dots`; noodles/sticks → `line`/`rect`;
   heat → `steam`; mound/tree → `triangle`; sauce/river → `wave`.
5. **Caption** (optional, ≤ 40 chars, poetic, lowercase): place or moment, e.g. "two golden yolks", "steam, 6:36am".
6. **Render & check**:
   `uv run python -m foodhunt.abstract render spec.json photo.jpg out.svg [--diptych]`
   Open/inspect the SVG. Would someone who was there recognise the moment? If not, change the
   facts, not the colours.
7. **Save into the album** (if the photo belongs to a trip):
   `PATCH /api/trips/<trip>/photos/<id>` with `{"symbol": <spec>, "caption": "..."}`
   — or in Python: `foodhunt.photos.update_photo(trip, id, symbol=spec, caption=...)`.

## Output
- Per photo: the `SymbolSpec` JSON + rendered SVG (symbol tile, or photo+symbol diptych).
- In the web album (`/album.html?trip=<trip>`): symbols appear beside each stamp and on the
  "Proust page" memory index (hover reveals the photo).

## Example spec
```json
{"visual_facts": ["dark boat-noodle broth", "meatballs", "steam"],
 "motif": "small bowls, many bowls", "background": 4, "caption": "small bowls, many bowls",
 "shapes": [{"type": "arc", "x": 50, "y": 56, "w": 62, "color": 0},
            {"type": "dots", "x": 50, "y": 62, "w": 22, "h": 30, "count": 3, "color": 1},
            {"type": "steam", "x": 50, "y": 30, "w": 30, "h": 28, "count": 3, "color": 3}]}
```

## Hosted version
On the website, "✨ Make symbol" calls `POST /api/trips/<trip>/photos/<id>/abstract`, which runs the
same procedure with Claude vision + structured output (`foodhunt.abstract.extract_spec`). Needs
`ANTHROPIC_API_KEY` on the server.
