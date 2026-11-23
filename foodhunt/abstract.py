"""Travel Photo Abstraction — the "Proust symbol".

Split of work (so the symbol is faithful, not invented):
  - Claude (vision) decides WHAT is most recognisable in the photo and WHERE/HOW to draw it
    → a small SymbolSpec (1–3 visual facts, ≤ 8 flat shapes on a 100×100 grid).
  - Code decides the COLOURS (sampled from the photo's pixels) and RENDERS the SVG.

Used by: the web API (POST /api/trips/{slug}/photos/{id}/abstract), the Claude Code skill
(.claude/skills/travel-photo-abstraction), and the CLI:
    uv run python -m foodhunt.abstract render spec.json photo.jpg out.svg
"""
from __future__ import annotations

import base64
import io
import json
import math
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ShapeType = Literal["circle", "ring", "rect", "line", "arc", "triangle", "wave", "dots", "steam"]


class Shape(BaseModel):
    type: ShapeType
    x: float = Field(50, ge=0, le=100, description="centre x on a 100x100 grid")
    y: float = Field(50, ge=0, le=100)
    w: float = Field(30, ge=0, le=100, description="width / diameter / length")
    h: float = Field(30, ge=0, le=100, description="height (rect, triangle, wave amplitude)")
    rotate: float = Field(0, ge=-180, le=180)
    color: int = Field(0, ge=0, le=4, description="index into the photo palette (0 = most dominant)")
    fill: bool = True
    opacity: float = Field(1, ge=0.15, le=1)
    count: int = Field(1, ge=1, le=12, description="dots/steam: how many")


class SymbolSpec(BaseModel):
    visual_facts: list[str] = Field(min_length=1, max_length=3,
                                    description="The 1-3 most recognisable things actually visible, e.g. 'red plastic stool', 'steam over pork leg'")
    motif: str = Field(description="2-4 word name of the symbol, e.g. 'steam over bowl'")
    shapes: list[Shape] = Field(min_length=1, max_length=8)
    background: int = Field(4, ge=0, le=4, description="palette index for the tile background (usually the lightest)")
    caption: str = Field("", max_length=40, description="optional short poetic caption, e.g. 'steam, 6:36am'")


# ---------------- colours from pixels ----------------

def palette(image_bytes: bytes, n: int = 5) -> list[str]:
    """Dominant colours, most → least frequent, with the lightest forced to the last slot."""
    from PIL import Image

    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    im.thumbnail((160, 160))
    q = im.quantize(colors=n + 3, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: (n + 3) * 3]
    counts = sorted(q.getcolors(), reverse=True)
    cols = []
    for _, idx in counts:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        if all(abs(r - R) + abs(g - G) + abs(b - B) > 40 for R, G, B in cols):  # skip near-duplicates
            cols.append((r, g, b))
        if len(cols) == n:
            break
    while len(cols) < n:
        cols.append(cols[-1])
    light = max(cols, key=lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])
    cols.remove(light)
    cols.append(light)
    return ["#%02x%02x%02x" % c for c in cols]


# ---------------- rendering ----------------

def _shape_svg(s: Shape, pal: list[str]) -> str:
    c = pal[s.color]
    paint = f'fill="{c}"' if s.fill else f'fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round"'
    t = f' transform="rotate({s.rotate:.1f} {s.x:.1f} {s.y:.1f})"' if s.rotate else ""
    o = f' opacity="{s.opacity:.2f}"' if s.opacity < 1 else ""
    x, y, w, h = s.x, s.y, s.w, s.h
    if s.type == "circle":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{w / 2:.1f}" {paint}{o}{t}/>'
    if s.type == "ring":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{w / 2:.1f}" fill="none" stroke="{c}" stroke-width="{max(1.5, h / 8):.1f}"{o}{t}/>'
    if s.type == "rect":
        return f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="1.5" {paint}{o}{t}/>'
    if s.type == "line":
        return f'<line x1="{x - w / 2:.1f}" y1="{y:.1f}" x2="{x + w / 2:.1f}" y2="{y:.1f}" stroke="{c}" stroke-width="2.2" stroke-linecap="round"{o}{t}/>'
    if s.type == "arc":  # lower half-circle: a bowl
        r = w / 2
        return f'<path d="M{x - r:.1f},{y:.1f} A{r:.1f},{r:.1f} 0 0 0 {x + r:.1f},{y:.1f} Z" {paint}{o}{t}/>'
    if s.type == "triangle":
        return f'<path d="M{x:.1f},{y - h / 2:.1f} L{x + w / 2:.1f},{y + h / 2:.1f} L{x - w / 2:.1f},{y + h / 2:.1f} Z" {paint}{o}{t}/>'
    if s.type == "wave":
        pts, steps = [], 24
        for i in range(steps + 1):
            px = x - w / 2 + w * i / steps
            pts.append(f"{px:.1f},{y + (h / 2) * math.sin(i / steps * 4 * math.pi):.1f}")
        return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round"{o}{t}/>'
    if s.type == "dots":  # a row of lights / sesame / stools
        n = max(1, s.count)
        gap = w / max(1, n - 1) if n > 1 else 0
        r = max(1.2, min(6, h / 6))
        return "".join(f'<circle cx="{x - w / 2 + gap * i:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{c}"{o}{t}/>' for i in range(n))
    if s.type == "steam":  # rising S-curves
        n = max(1, min(4, s.count))
        out = []
        for i in range(n):
            sx = x + (i - (n - 1) / 2) * (w / max(1, n))
            out.append(f'<path d="M{sx:.1f},{y + h / 2:.1f} c-4,-{h / 6:.1f} 4,-{h / 3:.1f} 0,-{h / 2:.1f} '
                       f's4,-{h / 3:.1f} 0,-{h / 2:.1f}" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"{o}/>')
        return "".join(out)
    return ""


def render_svg(spec: SymbolSpec, pal: list[str], size: int = 400) -> str:
    bg = pal[spec.background]
    body = "".join(_shape_svg(s, pal) for s in spec.shapes)
    title = json.dumps(", ".join(spec.visual_facts))[1:-1]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="{size}" height="{size}" role="img">'
            f'<title>{title}</title><rect width="100" height="100" fill="{bg}"/>{body}</svg>')


def compose_svg(spec: SymbolSpec, pal: list[str], photo_href: str, caption: str = "") -> str:
    """Diptych: photo (left) + Proust symbol (right) on paper, caption underneath."""
    cap = (caption or spec.caption).replace("&", "&amp;").replace("<", "&lt;")
    sym = render_svg(spec, pal).replace('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="400" height="400" role="img">',
                                         '<svg x="430" y="20" width="380" height="380" viewBox="0 0 100 100">')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 830 470">'
            f'<rect width="830" height="470" fill="#fffaf2"/>'
            f'<image href="{photo_href}" x="20" y="20" width="390" height="380" preserveAspectRatio="xMidYMid slice"/>'
            f'{sym}<text x="415" y="445" text-anchor="middle" font-family="Fraunces, Georgia, serif" font-style="italic" '
            f'font-size="20" fill="#4a4741">{cap}</text></svg>')


# ---------------- Claude vision → SymbolSpec ----------------

PROMPT = """You are making a "Proust symbol" for a travel food journal: a minimal abstract mark that,
like a smell, brings back the moment this photo was taken.

1. Name the 1-3 MOST RECOGNISABLE visual facts that are clearly visible (objects, light, steam,
   colours, arrangement) — specific to THIS photo, not generic ("red plastic stool", not "food").
2. Redraw them as 1-8 flat geometric shapes on a 100x100 grid using only: circle, ring, rect,
   line, arc (a bowl: lower half-circle), triangle, wave, dots (a row: lights/seeds), steam.
   Keep it sparse and balanced; leave breathing room; no letters or logos.
3. Colours are palette indices (0 = most dominant … 4 = lightest, usually the background).
   The palette was sampled from the photo: {palette}.
{context}"""


def extract_spec(image_bytes: bytes, media_type: str = "image/jpeg", context: str = "", client=None) -> SymbolSpec:
    import anthropic

    from .config import AGENT_MODEL

    client = client or anthropic.Anthropic()
    pal = palette(image_bytes)
    resp = client.messages.parse(
        model=AGENT_MODEL,
        max_tokens=4000,
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                         "data": base64.standard_b64encode(image_bytes).decode()}},
            {"type": "text", "text": PROMPT.format(palette=pal, context=f"Context: {context}" if context else "")},
        ]}],
        output_format=SymbolSpec,
    )
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise RuntimeError("Claude could not describe this photo")
    return resp.parsed_output


# ---------------- CLI (used by the Claude Code skill) ----------------

def main(argv: list[str]) -> None:
    """render <spec.json> <photo.jpg> <out.svg> [--diptych]   |   palette <photo.jpg>"""
    sys.stdout.reconfigure(encoding="utf-8")
    if argv[:1] == ["palette"]:
        print(json.dumps(palette(Path(argv[1]).read_bytes())))
    elif argv[:1] == ["render"]:
        spec = SymbolSpec.model_validate_json(Path(argv[1]).read_text(encoding="utf-8"))
        photo = Path(argv[2])
        pal = palette(photo.read_bytes())
        out = compose_svg(spec, pal, photo.resolve().as_uri()) if "--diptych" in argv else render_svg(spec, pal)
        Path(argv[3]).write_text(out, encoding="utf-8")
        print(json.dumps({"palette": pal, "out": argv[3]}))
    else:
        print(main.__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
