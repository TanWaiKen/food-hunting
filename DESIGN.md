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

## 11. v3 — Controls & Motion (after "the buttons look very AI")

Research: getdesign.md's DESIGN.md files (Nike, Apple, Framer, Clay, Airbnb, Stripe) define button
grammar but leave animation out of scope, so motion below is our own, built on their grammar.

**Controls**
- No emoji or icons inside buttons. Labels are plain verbs: "Plan a trip", "Directions", "Album".
- **One filled ink pill per view** (`ink #1f1a17`, paper text, trailing →). Chili is no longer a button colour.
- Every other action is a **text link**: 600 weight, underline that draws in from the left on hover, trailing ›.
- Pressing a pill **shrinks it to 0.97** (Framer); it never changes colour.

**Sentences**
- Every sentence has a role: kicker (caps, +0.14em), title (Fraunces 300), **lede** (Fraunces 300, 19–23px,
  one *italic* accent phrase), fact line (Inter 13px, muted), tip (Fraunces italic). Numbers under 21 are spelled out
  in ledes ("Fifteen plates"). Times use tabular figures. Ranges use en dashes.
- All times are **Kuala Lumpur time (MYT)**; local time sits under it in 11px muted.

**Motion** (all off under `prefers-reduced-motion`)
| Element | Motion | Timing |
|---|---|---|
| Text blocks, cards, legs | fade-up 14px, staggered 60–70ms | 600ms `cubic-bezier(.2,.7,.2,1)` |
| Primary pill arrow | nudge +4px | 250ms spring `cubic-bezier(.34,1.56,.64,1)` |
| Text link | underline grows 0→100% | 300ms ease-out |
| Card | lift −3px + softer, wider shadow | 300ms |
| Photo in card | slow push-in to 1.035–1.05 | 1.2–1.4s |
| Disclosure caret | rotates 45°→225° | 250ms |
| Symbol strip (home) | tiles rise in sequence | 40ms stagger, spring |

Alternatives on `/lab.html`: **B · Night Market** (Framer × Runway: dark, white/charcoal pills, marquee,
count-up, blur-in) and **C · Poster** (Nike × Vodafone: Anton caps, square buttons with fill-swipe, line wipe).

## 12. v4 — POSTER (chosen 2026-11-24) · supersedes §3 type, §4 controls, §11 controls

You picked direction **C · Poster** (Nike × Vodafone) from `/lab.html`. The paper canvas, the album's stamps and
film strip, the Proust symbols and the day colours stay. What changes:

| Token | Value |
|---|---|
| canvas / surface | `#fbfaf7` / `#ffffff` (dark: `#0f0f0f` / `#181818`) |
| ink | `#111111` — text, rules, buttons |
| chili | `#b8381a` — one accent: last headline line, primary-button hover fill, "must-eat", warnings |
| display | **Anton**, uppercase, line-height .86–.94 — page titles, section titles, big numbers, times |
| text | **Inter** — everything you read; emphasis = bold ink + chili-tint underline (no italics) |
| radius | 0 everywhere (photos, cards, tabs, pins, inputs) |
| depth | none — hard rules (3–4px ink or day colour on top of cards/stats) instead of shadows |

**Controls:** square, 2px ink border, 12px Inter 700 caps +0.12em. Hover = ink fill swipes in from the left
(350ms); primary is solid ink and its swipe is chili. Press = 1px drop. Text links: caps, 2px underline,
chili on hover, trailing ›. One solid primary per view still applies.

**Headlines:** each line is a `span.ln`; lines wipe in left→right (clip-path, 800ms, 120ms stagger). The last line
can be `.accent` (chili). Example: HATYAI / FOOD TRIP / *THREE DAYS.*

**Mobile ≤600px:** top bar keeps logo, Album and the primary only; headline line-height .94–.95.
