"""Web + Rednote research. Free web search via DuckDuckGo (ddgs); Rednote via its public
pages indexed by search engines, or the logged-in local xiaohongshu-mcp server when you run it."""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

from ddgs import DDGS


def _ddgs(query: str, limit: int, region: str) -> list[dict]:
    with DDGS() as d:
        return d.text(query, region=region, max_results=limit) or []


def web_search(query: str, limit: int = 8, region: str = "wt-wt") -> list[dict]:
    """Runs in a worker thread (ddgs has its own event loop, which clashes with the MCP server's)
    and retries once, because free search endpoints rate-limit."""
    last = None
    for attempt in range(2):
        try:
            with ThreadPoolExecutor(1) as ex:
                res = ex.submit(_ddgs, query, limit, region).result(timeout=40)
            return [{"title": r.get("title"), "url": r.get("href"), "snippet": r.get("body")} for r in res]
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"web search failed after retry: {type(last).__name__}: {last}")


def rednote_search(keyword: str, limit: int = 10) -> list[dict]:
    """Rednote (小红书) notes that search engines have indexed. No login needed.

    For full results (likes, comments, images) run xiaohongshu-mcp locally — see README.
    """
    out: list[dict] = []
    for q in (f"site:xiaohongshu.com {keyword}", f"小红书 {keyword}"):
        for r in web_search(q, limit=limit):
            if r["url"] and "xiaohongshu.com" in r["url"] and r not in out:
                out.append(r)
        if len(out) >= limit:
            break
    return out[:limit]


_SHARE_URL = re.compile(r"https?://(?:www\.)?(?:xhslink\.com|xiaohongshu\.com)/\S+")


def parse_rednote_share(text: str) -> dict:
    """Parse the text you get from Rednote's 'Share → Copy link'.

    e.g. '58 合艾必吃清单… http://xhslink.com/a/AbCd 复制本条信息，打开【小红书】App查看精彩内容！'
    """
    urls = _SHARE_URL.findall(text)
    title = _SHARE_URL.sub("", text)
    title = re.sub(r"复制本条信息.*$", "", title).strip(" ，,。\n")
    title = re.sub(r"^\d+\s+", "", title)  # leading share counter
    return {"title": title, "urls": urls, "tags": re.findall(r"#([^#\s]+)", text)}


def cross_check(name: str, city: str) -> dict:
    """Is this place real and still open? Count independent sources mentioning it."""
    hits = web_search(f'"{name}" {city}', limit=10)
    domains = sorted({re.sub(r"^www\.", "", (h["url"] or "").split("/")[2]) for h in hits if h["url"]})
    closed = any(re.search(r"permanently closed|ปิดกิจการ|已倒闭|结业", (h["snippet"] or ""), re.I) for h in hits)
    return {
        "name": name, "sources": len(domains), "domains": domains[:8],
        "maybe_closed": closed,
        "confidence": "high" if len(domains) >= 3 and not closed else "medium" if len(domains) >= 1 else "low",
        "top": hits[:3],
    }
