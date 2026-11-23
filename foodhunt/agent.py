"""Hosted trip-planning agent (Claude API + SDK Tool Runner).

Locally *you* talk to Claude Code, and Claude Code calls the MCP tools. On a server there is no
Claude Code, so this module is the agent: a Claude API tool-use loop with
  - our tools (tools.REMOTE_TOOLS, wrapped with @beta_tool → schema from type hints)
  - Claude's server-side web_search / web_fetch (runs on Anthropic's side — reliable from Vercel,
    where free search endpoints often block datacenter IPs)
Events are yielded as dicts so web.py can stream them to the browser (Server-Sent Events).
"""
from __future__ import annotations

import json
import queue
import threading
from collections.abc import Callable, Iterator
from functools import wraps

import anthropic
from anthropic import beta_tool

from . import tools as T
from .config import AGENT_EFFORT, AGENT_MODEL

SYSTEM = """You are Food Hunt, a food-trip planner for travellers from Malaysia and the region.

Goal: turn the user's request into a verified, time-aware eating plan, then call plan_trip_spec ONCE.

How to work:
1. Intent — from the message take city, dates, where they stay, must-eats, pace. If dates are missing,
   assume the next Friday–Sunday; if the hotel is missing, use the town centre. Note every assumption.
2. Gather — find 10–18 candidates. Use web_search, including Rednote/小红书 queries in Chinese
   (e.g. "site:xiaohongshu.com 槟城 美食", "小红书 Penang 必吃") and local-language queries, plus
   rednote_search / find_place / geocode / resolve_google_share_link.
3. Verify — keep a place only if 2+ independent sources mention it and nothing says it closed.
   Opening hours: if sources conflict, use the overlap; if none, leave `hours` empty (never invent).
   Coordinates: only from find_place/geocode/plus codes; otherwise leave empty. Set `confidence`
   and list `sources` URLs. Mark places that sell out, and night markets with their real days.
4. Plan — call plan_trip_spec with the full spec. It handles routing, crowds and meal slots.
5. Answer — 4–8 short lines: the days at a glance, assumptions, and anything unverified or
   without a location. Same language as the user. No tables."""

SERVER_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 12},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 8},
]


def _wrap(fn: Callable, emit: Callable[[dict], None]) -> Callable:
    """Report each tool call/result to the UI, and turn exceptions into readable tool errors."""

    @wraps(fn)
    def inner(*args, **kwargs):
        shown = {k: (v.model_dump() if hasattr(v, "model_dump") else v) for k, v in kwargs.items()}
        emit({"type": "tool_start", "tool": fn.__name__, "input": _short(shown)})
        try:
            out = fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — the model should see the failure and adapt
            emit({"type": "tool_error", "tool": fn.__name__, "error": str(e)[:300]})
            return json.dumps({"error": f"{type(e).__name__}: {e}"})
        emit({"type": "tool_done", "tool": fn.__name__})
        if fn is T.plan_trip_spec and isinstance(out, dict):
            emit({"type": "trip", "slug": out["slug"], "view": T._LAST_VIEW.get(out["slug"])})
        return json.dumps(out, ensure_ascii=False, default=str)

    return inner


def _short(obj, n: int = 160) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


def build_tools(emit: Callable[[dict], None]) -> list:
    return [beta_tool(_wrap(fn, emit)) for fn in T.REMOTE_TOOLS] + SERVER_TOOLS


def run(prompt: str, client: anthropic.Anthropic | None = None, max_iterations: int = 30) -> Iterator[dict]:
    """Yield UI events: status, text, tool_start/tool_done/tool_error, search, trip, done, error."""
    events: queue.Queue[dict | None] = queue.Queue()
    emit = events.put
    client = client or anthropic.Anthropic()

    def worker():
        try:
            runner = client.beta.messages.tool_runner(
                model=AGENT_MODEL,
                max_tokens=16000,
                system=SYSTEM,
                tools=build_tools(emit),
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": AGENT_EFFORT},
                # refusal safety net: if Opus declines, the API retries on a fallback model
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                max_iterations=max_iterations,
            )
            final = None
            for message in runner:
                final = message
                for block in message.content:
                    if block.type == "text" and block.text.strip():
                        emit({"type": "text", "text": block.text})
                    elif block.type == "server_tool_use":
                        q = (block.input or {}).get("query") or (block.input or {}).get("url") or ""
                        emit({"type": "search", "tool": block.name, "query": str(q)[:160]})
            if final is not None and final.stop_reason == "refusal":
                emit({"type": "error", "error": "The model declined this request."})
            usage = getattr(final, "usage", None)
            emit({"type": "done", "stop_reason": getattr(final, "stop_reason", None),
                  "usage": {"input": getattr(usage, "input_tokens", None), "output": getattr(usage, "output_tokens", None)}})
        except anthropic.AuthenticationError:
            emit({"type": "error", "error": "ANTHROPIC_API_KEY is missing or invalid on the server."})
        except anthropic.RateLimitError:
            emit({"type": "error", "error": "Rate limited by the Claude API — try again in a minute."})
        except anthropic.APIStatusError as e:
            emit({"type": "error", "error": f"Claude API error {e.status_code}: {e.message}"})
        except anthropic.APIConnectionError:
            emit({"type": "error", "error": "Could not reach the Claude API."})
        except Exception as e:  # noqa: BLE001
            emit({"type": "error", "error": f"{type(e).__name__}: {e}"})
        finally:
            events.put(None)

    emit({"type": "status", "text": f"Planning with {AGENT_MODEL}…"})
    threading.Thread(target=worker, daemon=True).start()
    while (ev := events.get()) is not None:
        yield ev
