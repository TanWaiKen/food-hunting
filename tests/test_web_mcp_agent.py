"""Web API, remote MCP endpoint and the agent's event wiring (Claude API mocked — no key, no cost)."""
import json
import types

import pytest
from fastapi.testclient import TestClient

from foodhunt import agent, config, web
from foodhunt import tools as T

MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
               "MCP-Protocol-Version": "2025-06-18"}




def rpc(c, method, params=None, id_=1, headers=MCP_HEADERS):
    return c.post("/mcp/", headers=headers, json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}})


def test_health_and_trip_api(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["model"] == "claude-opus-5-5"
    trips = client.get("/api/trips").json()
    assert any(t["slug"] == "hatyai" for t in trips)
    v = client.get("/api/trips/hatyai").json()
    assert v["trip"]["title"] == "Hatyai Food Trip" and len(v["days"]) == 3
    assert client.get("/api/trips/nope").status_code == 404
    assert "Food Hunt" in client.get("/").text


def test_remote_mcp_lists_and_calls_tools(client):
    init = rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "pytest", "version": "1"}})
    assert init.status_code == 200, init.text
    assert init.json()["result"]["serverInfo"]["name"] == "foodhunt"
    names = {t["name"] for t in rpc(client, "tools/list", id_=2).json()["result"]["tools"]}
    assert {"plan_trip_spec", "crowd_forecast", "rednote_search"} <= names
    assert "plan_trip" not in names                        # file-path tool is local-only
    res = rpc(client, "tools/call", {"name": "parse_rednote_share",
                                      "arguments": {"text": "合艾必吃 http://xhslink.com/a/Ab1 复制本条信息"}}, id_=3).json()
    payload = json.loads(res["result"]["content"][0]["text"])
    assert payload["urls"] == ["http://xhslink.com/a/Ab1"]


def test_access_code_protects_agent_and_mcp(client, monkeypatch):
    monkeypatch.setattr(web, "ACCESS_TOKEN", "s3cret")
    assert client.post("/api/agent", json={"prompt": "Ipoh 1 day"}).status_code == 401
    assert rpc(client, "tools/list").status_code == 401
    ok = rpc(client, "tools/list", headers={**MCP_HEADERS, "Authorization": "Bearer s3cret"})
    assert ok.status_code == 200


class FakeRunner:
    """Stands in for client.beta.messages.tool_runner: 'Claude' calls two tools, then answers."""

    def __init__(self, **kw):
        self.kw = kw
        self.tools = {t.name: t for t in kw["tools"] if hasattr(t, "call")}

    def __iter__(self):
        yield _msg([_block("server_tool_use", name="web_search", input={"query": "site:xiaohongshu.com 合艾 美食"})], "tool_use")
        self.tools["crowd_forecast"].call({"name": "X", "kind": "meal", "hours": "10:00-20:00", "weekday": 4})
        spec = {"trip": "Unit Test Trip", "city": "Hat Yai, Thailand", "center": [7.0074, 100.469],
                "start": {"name": "Hotel", "lat": 7.0058, "lng": 100.4717},
                "days": [{"date": "2026-12-04"}],
                "places": [{"name": "Pork leg", "kind": "breakfast", "hours": "06:30-14:30", "lat": 7.003, "lng": 100.4728}]}
        self.tools["plan_trip_spec"].call({"spec": spec})
        yield _msg([_block("text", text="Day 1: pork leg at 07:00.")], "end_turn")


def _block(type_, **kw):
    return types.SimpleNamespace(type=type_, **kw)


def _msg(content, stop):
    return types.SimpleNamespace(content=content, stop_reason=stop,
                                 usage=types.SimpleNamespace(input_tokens=10, output_tokens=20))


def test_agent_streams_tool_events_and_trip(monkeypatch, tmp_path):
    monkeypatch.setattr("foodhunt.store.DATA_DIR", tmp_path)
    monkeypatch.setattr("foodhunt.pipeline.DATA_DIR", tmp_path)
    monkeypatch.setattr("foodhunt.pipeline.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("foodhunt.geo.route_leg", lambda a, b, mode="walking": {
        "mode": mode, "meters": 100, "minutes": 2, "steps": ["Go"], "geometry": [[a[1], a[0]], [b[1], b[0]]], "source": "test"})
    captured = {}

    def fake_tool_runner(**kw):
        captured.update(kw)
        return FakeRunner(**kw)

    fake = types.SimpleNamespace(beta=types.SimpleNamespace(messages=types.SimpleNamespace(tool_runner=fake_tool_runner)))
    events = list(agent.run("Hat Yai 1 day", client=fake))
    kinds = [e["type"] for e in events]
    assert kinds[0] == "status" and kinds[-1] == "done"
    assert "search" in kinds and "tool_start" in kinds and "text" in kinds
    trip = next(e for e in events if e["type"] == "trip")
    assert trip["slug"] == "unit-test-trip" and "07:00" <= trip["view"]["days"][0]["stops"][0]["arrive"] < "08:00"
    # request shape: our model, effort, fallbacks, server-side web tools
    assert captured["model"] == "claude-opus-5-5" and captured["output_config"] == {"effort": "high"}
    assert captured["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in captured["betas"]
    assert {"web_search_20260209", "web_fetch_20260209"} <= {t.get("type") for t in captured["tools"] if isinstance(t, dict)}


def test_agent_reports_missing_key(monkeypatch):
    import anthropic
    import httpx2

    def boom(**kw):
        raise anthropic.AuthenticationError("no key", response=httpx2.Response(401, request=httpx2.Request("POST", "https://x")), body=None)

    fake = types.SimpleNamespace(beta=types.SimpleNamespace(messages=types.SimpleNamespace(tool_runner=boom)))
    events = list(agent.run("x", client=fake))
    assert any(e["type"] == "error" and "ANTHROPIC_API_KEY" in e["error"] for e in events)


def test_place_images_served_by_app(client):
    """Restaurant images work even when the CDN doesn't have public/img; no path tricks."""
    from foodhunt.config import PUBLIC_DIR
    imgs = sorted((PUBLIC_DIR / "img").glob("*.jpg"))
    if imgs:
        r = client.get(f"/img/{imgs[0].name}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get("/img/..%2F..%2Fpyproject.toml").status_code == 404
    assert client.get("/img/nope.jpg").status_code == 404
