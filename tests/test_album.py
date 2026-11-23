"""Album: EXIF GPS/time matching, upload API, abstraction renderer, Claude vision call (mocked)."""
import io
import types

import pytest
from PIL import Image

from foodhunt import abstract, config, photos, web

VIEW = {
    "trip": {"title": "T", "city": "Hat Yai", "start": {"name": "H", "lat": 7.0058, "lng": 100.4717}},
    "days": [{"date": "2026-12-04", "weekday": "Fri", "map_link": "", "walk_m": 0, "stops": [
        {"arrive": "06:36", "leave": "07:16", "leg": {"geometry": []},
         "place": {"name": "Ko Chew", "display": "Ko Chew", "lat": 7.00296, "lng": 100.47279}},
        {"arrive": "18:00", "leave": "19:15", "leg": {"geometry": []},
         "place": {"name": "Night market", "display": "Night market", "lat": 7.00599, "lng": 100.47152}},
    ]}],
    "leftover": [], "no_location": [],
}


def jpeg(color=(200, 120, 40), gps=None, when=None) -> bytes:
    im = Image.new("RGB", (64, 48), color)
    ex = Image.Exif()
    if when:
        ex[306] = when
    if gps:
        def dms(v):
            v = abs(v); d = int(v); m = int((v - d) * 60)
            return (float(d), float(m), round(((v - d) * 60 - m) * 60, 2))
        ex[0x8825] = {1: "N", 2: dms(gps[0]), 3: "E", 4: dms(gps[1])}
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=ex)
    return buf.getvalue()


@pytest.fixture()
def tmpdata(monkeypatch, tmp_path):
    monkeypatch.setattr(photos, "DATA_DIR", tmp_path)
    return tmp_path


def test_gps_match_beats_time(tmpdata):
    p = photos.add_photo("t", VIEW, jpeg(gps=(7.00300, 100.47285), when="2026:12:04 18:30:00"))
    assert p["stop_key"] == "0-0" and p["by"] == "gps" and p["distance_m"] < 50


def test_time_match_when_no_gps(tmpdata):
    p = photos.add_photo("t", VIEW, jpeg(when="2026:12:04 18:40:00"))
    assert p["stop_key"] == "0-1" and p["by"] == "time"


def test_unsorted_when_nothing_matches(tmpdata):
    p = photos.add_photo("t", VIEW, jpeg())
    assert p["stop_key"] is None
    assert len(p["palette"]) == 5 and all(c.startswith("#") for c in p["palette"])


def test_symbol_render_uses_photo_palette():
    spec = abstract.SymbolSpec(visual_facts=["steam over bowl"], motif="steam",
                               shapes=[abstract.Shape(type="arc", color=0), abstract.Shape(type="steam", count=3, color=1)])
    pal = ["#aa0000", "#00aa00", "#0000aa", "#333333", "#fafafa"]
    svg = abstract.render_svg(spec, pal)
    assert svg.startswith("<svg") and "#aa0000" in svg and "#00aa00" in svg and 'fill="#fafafa"' in svg
    with pytest.raises(Exception):
        abstract.SymbolSpec(visual_facts=[], motif="x", shapes=[])   # facts + shapes required


def test_upload_api_and_patch(tmpdata, monkeypatch, client):
    monkeypatch.setattr(web, "_view", lambda slug: VIEW)
    if True:
        c = client
        r = c.post("/api/trips/t/photos", files=[("files", ("a.jpg", jpeg(gps=(7.006, 100.4715)), "image/jpeg")),
                                                  ("files", ("b.txt", b"not an image", "text/plain"))])
        added = r.json()["added"]
        assert added[0]["stop_key"] == "0-1" and "error" in added[1]
        pid = added[0]["id"]
        assert c.get(f"/api/trips/t/photos/{pid}.jpg").headers["content-type"] == "image/jpeg"
        spec = {"visual_facts": ["lights"], "motif": "lights", "shapes": [{"type": "dots", "count": 5}]}
        assert c.patch(f"/api/trips/t/photos/{pid}", json={"symbol": spec, "caption": "night"}).status_code == 200
        album = c.get("/api/trips/t/album").json()["album"]["photos"][0]
        assert album["caption"] == "night" and album["symbol_svg"].startswith("<svg")


def test_extract_spec_calls_claude_with_image_and_schema():
    seen = {}

    def parse(**kw):
        seen.update(kw)
        spec = abstract.SymbolSpec(visual_facts=["orange stool"], motif="stool", shapes=[abstract.Shape(type="rect")])
        return types.SimpleNamespace(stop_reason="end_turn", parsed_output=spec)

    fake = types.SimpleNamespace(messages=types.SimpleNamespace(parse=parse))
    out = abstract.extract_spec(jpeg(), context="Taken at Ko Chew", client=fake)
    assert out.visual_facts == ["orange stool"]
    assert seen["model"] == config.AGENT_MODEL and seen["output_format"] is abstract.SymbolSpec
    content = seen["messages"][0]["content"]
    assert content[0]["type"] == "image" and "Ko Chew" in content[1]["text"]
