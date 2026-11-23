"""ONE place where every tool is defined.

The same Python functions are exposed three ways:
  1. local MCP server (stdio)            → Claude Code / Claude Desktop on your PC   (server.py)
  2. remote MCP server (HTTP, /mcp)      → claude.ai connectors, other agents          (web.py)
  3. hosted agent tools (Claude API)     → the "Plan a trip" button on the website     (agent.py)
Type hints + docstrings become the JSON schema in all three, so they can't drift apart.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from . import crowd, geo, pipeline, places, research
from . import hours as H

Kind = Literal["breakfast", "meal", "hotpot", "snack", "dessert", "mall", "night_market"]


# ---------------- trip spec (what the agent fills in) ----------------

class PlaceSpec(BaseModel):
    name: str = Field(description="Shop name as locals/Google know it")
    kind: Kind = Field(description="Decides which meal slot it can fill")
    display: str | None = Field(None, description="Pretty title, e.g. '秋哥猪脚饭 Ko Chew Pork Leg'")
    hours: str | None = Field(None, description="e.g. '06:30-14:30' or 'Mo,Tu,Th-Su 11:00-20:00; We off' or '10:00-14:00,16:00-20:00'. Omit if unknown — never guess")
    lat: float | None = Field(None, description="Only if taken from a reliable source")
    lng: float | None = None
    plus_code: str | None = Field(None, description="Google plus code like '2F3C+4WG' if a source gives one")
    address_query: str | None = Field(None, description="Street address used when the name is not on the map")
    search: str | None = Field(None, description="Alternative name to search maps with (e.g. Thai name)")
    sells_out: bool = False
    must: bool = Field(False, description="User explicitly asked for it")
    not_before: str | None = Field(None, description="'18:00' for night markets / places best after dark")
    dwell: int = Field(40, description="Minutes spent eating")
    confidence: Literal["high", "medium", "low"] = Field("medium", description="high = official/Google, medium = 2+ sources agree, low = single/unclear")
    order: str | None = Field(None, description="What to order")
    tip: str | None = None
    sources: list[str] = Field(default_factory=list, description="URLs that back the hours/existence")


class DaySpec(BaseModel):
    date: str = Field(description="YYYY-MM-DD")
    start_time: str = "07:00"
    end_time: str = "23:00"


class StartPoint(BaseModel):
    name: str
    lat: float
    lng: float


class TripSpec(BaseModel):
    trip: str = Field(description="Title, e.g. 'Penang Food Trip'")
    city: str = Field(description="'City, State/Province, Country' — used for map lookups")
    timezone: str = Field("Asia/Kuala_Lumpur", description="IANA zone of the destination, e.g. 'Asia/Bangkok'; times are shown in MYT")
    center: tuple[float, float] = Field(description="[lat, lng] of the town centre")
    start: StartPoint = Field(description="Hotel / where each day starts")
    days: list[DaySpec]
    places: list[PlaceSpec]
    max_stops_per_day: int = 6
    walk_max_m: int = 1200


# ---------------- tools ----------------

def find_place(name: str, city: str) -> dict | None:
    """Look up one food place: coordinates, address, rating, reviews, opening hours, photos.
    Google Places when GOOGLE_MAPS_API_KEY is set, else OpenStreetMap (no ratings/photos)."""
    return places.lookup(name, city)


def food_nearby(lat: float, lng: float, radius_m: int = 800) -> list[dict]:
    """Food places around a point (hotel, mall, night market), most popular/closest first."""
    return places.nearby(lat, lng, radius_m)[:25]


def geocode(query: str) -> dict | None:
    """Address or landmark → lat,lng (OpenStreetMap)."""
    return geo.geocode_osm(query)


def resolve_google_share_link(url: str) -> dict:
    """Turn a share.google / maps.app.goo.gl link into the place name (and coordinates if present)."""
    return places.resolve_share_link(url)


def web_search(query: str, limit: int = 8) -> list[dict]:
    """General web search (DuckDuckGo, no key). For reviews, blogs, 'best X in Y'."""
    return research.web_search(query, limit)


def rednote_search(keyword: str, limit: int = 10) -> list[dict]:
    """Rednote/小红书 notes about a keyword (e.g. '合艾 美食'), via the search-engine index (no login)."""
    return research.rednote_search(keyword, limit)


def parse_rednote_share(text: str) -> dict:
    """Parse text copied from Rednote's Share button → title, links, hashtags."""
    return research.parse_rednote_share(text)


def verify_place(name: str, city: str) -> dict:
    """Cross-check a place on the web: number of independent sources, closed-down signals, confidence."""
    return research.cross_check(name, city)


def crowd_forecast(name: str, kind: Kind, hours: str, weekday: int, reviews: int | None = None, address: str = "") -> dict:
    """Busy level by hour (0-100) + quietest/busiest hour. hours like '06:30-12:00'. weekday 0=Mon.
    Real data from BestTime if BESTTIME_API_KEY_PRIVATE is set, else a labelled estimate."""
    return crowd.for_place({"name": name, "kind": kind, "reviews": reviews, "address": address}, H.parse_simple(hours), weekday)


def walking_directions(from_lat: float, from_lng: float, to_lat: float, to_lng: float,
                       mode: Literal["walking", "driving"] = "walking") -> dict:
    """Turn-by-turn directions, distance and minutes between two points + a Google Maps link."""
    leg = geo.route_leg((from_lat, from_lng), (to_lat, to_lng), mode)
    leg.pop("geometry", None)
    leg["google_maps"] = geo.gmaps_dir_link([(from_lat, from_lng), (to_lat, to_lng)], mode)
    return leg


def plan_trip(trip_file: str, refresh: bool = False) -> dict:
    """Plan a trip from a yaml file on disk (trips/<name>.yaml) → output/<name>.html + .notion.md. Local use."""
    return pipeline.run(trip_file, refresh)


def plan_trip_spec(spec: TripSpec) -> dict:
    """Plan a trip from a full spec: geocodes every place, checks opening hours per weekday, fills
    breakfast→supper slots, routes walking legs and estimates crowds. Call ONCE with all places.
    Returns a short summary (stops per day, places without location, unverified hours) and the
    trip's slug; the full itinerary is shown to the user automatically."""
    slug = pipeline.slugify(spec.trip)
    res = pipeline.build(spec.model_dump(), slug)
    _LAST_VIEW[slug] = res["view"]
    return res["summary"]


_LAST_VIEW: dict[str, dict] = {}  # slug → view model, picked up by the agent stream / web API

LOCAL_TOOLS = [find_place, food_nearby, geocode, resolve_google_share_link, web_search, rednote_search,
               parse_rednote_share, verify_place, crowd_forecast, walking_directions, plan_trip, plan_trip_spec]
# Hosted: no file-path tool; our DuckDuckGo `web_search` is replaced by Claude's own server-side web search
REMOTE_TOOLS = [t for t in LOCAL_TOOLS if t not in (plan_trip, web_search)]
