"""Paths + environment. Works locally (writes into the project) and on Vercel (read-only
filesystem except /tmp)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ON_VERCEL = bool(os.getenv("VERCEL"))

# Bundled, read-only data that ships with the deployment (e.g. the Hat Yai sample trip)
BUNDLED_DATA = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
TRIPS_DIR = ROOT / "trips"

# Writable local data: the place-lookup cache, and trips/albums when no Blob store is connected
# (see store.py). /tmp on Vercel — wiped between cold starts, so connect Vercel Blob there.
DATA_DIR = Path(os.getenv("FOODHUNT_DATA_DIR") or ("/tmp/foodhunt/data" if ON_VERCEL else BUNDLED_DATA))
OUTPUT_DIR = Path(os.getenv("FOODHUNT_OUTPUT_DIR") or ("/tmp/foodhunt/output" if ON_VERCEL else ROOT / "output"))

# Hosted agent (Claude API). Effort "high": multi-step research where accuracy matters.
AGENT_MODEL = os.getenv("FOODHUNT_MODEL", "claude-opus-5-5")
AGENT_EFFORT = os.getenv("FOODHUNT_EFFORT", "high")

# Shared secrets that protect the paid endpoints on a public deployment. Unset = open (local dev).
ACCESS_TOKEN = os.getenv("FOODHUNT_ACCESS_TOKEN") or None   # /api/agent and /mcp

