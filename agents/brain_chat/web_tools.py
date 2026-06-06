"""Native, provider-free web tools for the chat live-retrieval phase.

Two read-only tools the chat planner can call inline:
  - web_search(query): DuckDuckGo HTML results (title, url, snippet), no API key.
  - web_fetch(url): GET a URL and return readable text (HTML stripped, truncated).

Read-only by design: code/shell execution stays behind the gated /agent path, so
plain chat can gather information but never mutates the machine.
"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import unquote

import httpx

_UA = "Mozilla/5.0 (compatible; KIA/1.0; +local)"
_MAX_FETCH = 40_000
_SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"

# OpenAI-format tool schemas advertised to the planner model.
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information. Returns a ranked list of "
                "results with title, URL, and snippet. Use for recent facts, news, "
                "docs, or anything past the training data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                    "k": {"type": "integer", "description": "Max results (default 5)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": (
                "Fetch a single http(s) URL and return its readable text content "
                "(HTML stripped, truncated). Use to read a page found via web_search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The http(s) URL to fetch."},
                },
                "required": ["url"],
            },
        },
    },
]

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_HTML_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]*\n[ \t\n]*")
_RESULT_RE = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_SNIPPET_RE = re.compile(
    r'<a[^>]*class="result__snippet"[^>]*>(?P<snip>.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)


def _clean(text: str) -> str:
    """Strip tags and entities from an HTML fragment to plain text."""
    text = _HTML_RE.sub("", text)
    return html.unescape(text).strip()


def _unwrap_ddg(url: str) -> str:
    """DuckDuckGo wraps result links in a redirect; pull out the real uddg= target."""
    m = re.search(r"[?&]uddg=([^&]+)", url)
    if m:
        return unquote(m.group(1))
    if url.startswith("//"):
        return "https:" + url
    return url


async def web_search(query: str, k: int = 5) -> str:
    """Return up to k web results as a readable text block."""
    k = max(1, min(int(k or 5), 10))
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.post(
                _SEARCH_ENDPOINT, data={"q": query}, headers={"User-Agent": _UA}
            )
            body = resp.text
    except Exception as e:  # noqa: BLE001 - report to the loop as text
        return f"[web_search error: {type(e).__name__}: {e}]"

    titles = list(_RESULT_RE.finditer(body))
    snippets = [_clean(m.group("snip")) for m in _SNIPPET_RE.finditer(body)]
    if not titles:
        return f"[web_search: no results for '{query}']"
    lines: list[str] = [f"Search results for '{query}':"]
    for i, m in enumerate(titles[:k]):
        title = _clean(m.group("title"))
        url = _unwrap_ddg(m.group("url"))
        snip = snippets[i] if i < len(snippets) else ""
        lines.append(f"{i + 1}. {title}\n   {url}\n   {snip}")
    return "\n".join(lines)


async def web_fetch(url: str) -> str:
    """GET an http(s) URL and return readable text (HTML stripped, truncated)."""
    if not url.lower().startswith(("http://", "https://")):
        return "[web_fetch error: only http(s) URLs are allowed]"
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": _UA})
            raw = resp.text
    except Exception as e:  # noqa: BLE001
        return f"[web_fetch error for {url}: {type(e).__name__}: {e}]"
    stripped = _TAG_RE.sub(" ", raw)
    text = _WS_RE.sub("\n", _clean(stripped))
    return text[:_MAX_FETCH] + ("\n…[truncated]" if len(text) > _MAX_FETCH else "")


async def dispatch(name: str, args: dict[str, Any]) -> str:
    """Execute a native web tool by name."""
    if name == "web_search":
        return await web_search(str(args.get("query", "")), int(args.get("k", 5) or 5))
    if name == "web_fetch":
        return await web_fetch(str(args.get("url", "")))
    return f"[error: unknown tool '{name}']"
