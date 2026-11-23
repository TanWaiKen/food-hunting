"""MCP server `foodhunt`.

Local:   uv run foodhunt-mcp            (stdio — Claude Code / Claude Desktop start it for you)
Remote:  mounted at /mcp by web.py      (streamable HTTP — deploy to Vercel, add as a connector)
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .tools import LOCAL_TOOLS, REMOTE_TOOLS

INSTRUCTIONS = (
    "Food Hunt tools: research food places (Rednote, web, maps), verify them, forecast crowds, "
    "route walking legs and build a time-aware multi-day eating plan with plan_trip_spec."
)


def make_server(remote: bool = False) -> MCPServer:
    mcp = MCPServer("foodhunt", instructions=INSTRUCTIONS)
    for fn in REMOTE_TOOLS if remote else LOCAL_TOOLS:
        mcp.add_tool(fn)
    return mcp


mcp = make_server()


def main() -> None:
    import logging
    import sys

    # Windows consoles default to cp1252; search libraries log Chinese/Thai text and crash the tool.
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    for noisy in ("primp", "ddgs", "httpx", "httpx2", "rquest"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    mcp.run()


if __name__ == "__main__":
    main()
