"""
webscout.py — The Web Scout (البحث في الويب)
=============================================
A dependency-free web search tool so the AI can read about new techniques on
the open web (e.g. to learn a better approach before editing its own code).

Uses DuckDuckGo's HTML endpoint (no API key required) and extracts the top
result titles, URLs and snippets. Network access is allowed but the results
are just text returned to the model — no code is executed from the web.
"""

import re
import html
import urllib.parse
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (MATRIX WebScout)"}


def web_search(query: str, max_results: int = 5) -> dict:
    """Return a list of {title, url, snippet} for a query."""
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return {"query": query, "error": str(exc), "results": []}

    html_text = resp.text
    results = []

    # Each result link looks like: <a ... class="result__a" href="URL">TITLE</a>
    link_re = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    snip_re = re.compile(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', re.S)

    links = link_re.findall(html_text)
    snippets = snip_re.findall(html_text)

    def clean(s: str) -> str:
        return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()

    for i, (url, title) in enumerate(links[:max_results]):
        # DuckDuckGo wraps the real URL in a redirect; extract uddg param.
        m = re.search(r"uddg=([^&]+)", url)
        real = urllib.parse.unquote(m.group(1)) if m else url
        results.append(
            {
                "title": clean(title),
                "url": real,
                "snippet": clean(snippets[i]) if i < len(snippets) else "",
            }
        )

    return {"query": query, "results": results}
