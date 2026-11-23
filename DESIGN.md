# Food Hunt — Design System ("Field Journal")

Format follows [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (Google Stitch DESIGN.md).
Lineage: **Oura** (warm-paper field journal, thin editorial serif, earth tones, one decisive action
colour) × **Runway** (photography *is* the UI, dark cinema stage, invisible chrome) × the travel
scrapbook: postage stamps, film strips, folded maps, a monumental cover word.

## 1. Visual Theme & Atmosphere

A food trip remembered as a printed field journal. Pages are warm paper, never white. Photos carry
the emotion; the interface recedes to hairlines and quiet labels. Two worlds alternate:

- **Paper world** (`canvas #f6f0e6`) — planning, reading, the day-by-day route.
- **Espresso world** (`espresso #2b1d18`) — the album stage, where photos sit like prints and stamps
  on a dark table (lit, cinematic, Runway-style).

Signature objects: the **postage stamp** (perforated photo frame), the **film strip** (vertical run
of stamps held by a binder clip), the **route map** (a hand-drawn line on paper with numbered
stamps), the **cover word** (a city name set vertically in condensed caps over a photo), and the
**Proust symbol** — a minimal abstract mark distilled from a photo (see §10).

## 2. Color Palette & Roles

| Token | Hex | Role |
|---|---|---|
| canvas | `#f6f0e6` | Default page surface (warm paper) |
| paper | `#fffaf2` | Raised cards, stamps' paper border |
| kraft | `#e8dcc8` | Album page tint, tape |
| hairline | `#e2d8c8` | 1px rules and card borders |
| ink | `#1f1a17` | Primary text |
| stone | `#4a4741` | Secondary text, outlines, neutral buttons |
| ash | `#857d74` | Captions, metadata |
| espresso | `#2b1d18` | Album stage / dark bands |
| espresso-2 | `#3a2a23` | Raised surfaces on espresso |
| chili | `#b8381a` | **The single action colour** — primary CTA only ("Plan a trip", "Make album") |
| ochre | `#c08a3e` | Earth accent: crowd bars, highlights |
| clay | `#8a4b3b` | Earth accent: arrival marker, stamps' ink |
| olive | `#5c6f5d` | Earth accent: "good"/quiet states, sage bands |

Map/day identity colours are a *data* job and keep the validated categorical set
(`#d9480f #1098ad #7048e8 #b08800`, dark: `#e05a16 #1c95a8 #7c5cf0 #b8860b`) — run
the dataviz validator before changing them.

## 3. Typography Rules

| Role | Family | Size / Weight | Notes |
|---|---|---|---|
| cover-word | **Anton** | 96–180px / 400, uppercase, letter-spacing 0.02em | Album cover & day chapters only. Never in body UI. |
| display | **Fraunces** (opsz 144) | 40–72px / 300 | Thin, high-contrast; scale (not boldness) makes hierarchy |
| heading | Fraunces | 22–32px / 400 | Place names, day titles |
| eyebrow | Inter | 11–12px / 700, uppercase, +0.12em | Section context ("DAY 1 · FRI 4 DEC") |
| body | Inter | 15–16px / 400, line-height 1.5 | Everything you read |
| caption | Inter | 12–13px / 500 | Times, metadata |
| script note | Fraunces italic | 14–18px / 300 | Album captions ("steam, 6:36am") |

Serif for feeling, sans for facts. CJK/Thai fall back to Noto Serif SC / Noto Sans Thai.

## 4. Component Stylings

- **Buttons** — pill (`9999px`). Primary: chili fill, paper text — one per view. Secondary: transparent, 1px stone outline, ink text.
- **Cards** — paper fill, 1px hairline, radius 20px, warm low shadow `0 1px 2px rgb(43 29 24/.06), 0 12px 32px rgb(43 29 24/.07)`.
- **Eyebrow labels** — uppercase Inter 700 in ash; no background.
- **Postage stamp** — photo inside a paper border 10px with scalloped perforations (CSS radial-gradient mask), slight rotation −3°…3°, soft drop shadow; caption in eyebrow style below the photo.
- **Film strip** — vertical stack of stamps on espresso, a black binder clip at the top, left/right labels in widely-tracked serif small caps.
- **Proust symbol** — square paper tile, 1–8 flat shapes from the photo's own palette, no outlines heavier than 2px, no text inside.
- **Crowd chart** — ochre bars, clay arrival bar labelled "you", closed hours as kraft ticks. One series → no legend.
- **Tape** — kraft rectangles at 40% opacity, rotated, to "stick" photos on album pages.

## 5. Layout Principles

- Trip page: reading column (max 600px) + sticky map; mobile: map on top, list below.
- Album: full-bleed chapters. Cover → one spread per day (route map + stamps + symbols) → film strip of highlights → index.
- Generous vertical silence between sections (64–120px). Treat empty paper as structure.

## 6. Depth & Elevation

Flat paper. Only stamps and photos lift (warm, soft shadow). No glass, no gradients in chrome —
colour comes from photography and the earth accents.

## 7. Do's and Don'ts

**Do** keep chili unique to the primary action · default to canvas, not white · let photos run large ·
use earth tones in bands, data and symbols · rotate stamps slightly so pages feel handmade.

**Don't** use chili for links or decoration · put Anton in body UI · add heavy borders/shadows ·
crowd a page · invent colours for symbols (they come from the photo) · cycle categorical colours.

## 8. Responsive Behavior

≤ 900px: single column, map collapses to a 34vh band with a Map/List toggle, cover word shrinks to
clamp(72px, 22vw, 140px), stamps go 2-up, film strip stays single column.

## 9. Agent Prompt Guide

"Warm-paper travel journal. Canvas #f6f0e6, ink #1f1a17. Thin Fraunces display, Inter body, Anton
only for the vertical cover word. One chili #b8381a pill CTA per view. Photos inside perforated
postage-stamp frames, slightly rotated, on kraft or espresso #2b1d18. Earth accents ochre/clay/olive
for data and bands. Hairlines, soft warm shadows, no gradients."

## 10. The Proust Symbol (image "Proust effect")

A smell can bring back a whole afternoon; a few shapes can do the same for a photo. For every photo
we keep 1–3 **most recognisable visual facts** (the red stool, the steam over the pork leg, the
fairy lights in the treehouse) and redraw them as a minimal abstract mark in the photo's **own
colours**. The symbol sits next to the photo (diptych) or alone as a memory index. Rules:
facts must be visible in the photo · ≤ 8 flat shapes · colours sampled from pixels, never invented ·
no letters or logos · one short caption (place + time), optional.
