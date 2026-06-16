"""
Web search - a real "hand" for the agent (Stage 2: tool building).

The agent uses this to look things up on the internet instead of being a
closed chatbot. Exa is the default provider; the API key is read from the
environment (EXA_API_KEY), never hardcoded.
"""
from __future__ import annotations

import requests

import config


def search(query: str, num_results: int = 5) -> dict:
    provider = config.SEARCH_PROVIDER
    if provider == "exa":
        if not config.EXA_API_KEY:
            return {"ok": False, "error": "EXA_API_KEY not set in environment"}
        try:
            resp = requests.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": config.EXA_API_KEY,
                         "Content-Type": "application/json"},
                json={
                    "query": query,
                    "numResults": max(1, min(num_results, 10)),
                    "contents": {"text": {"maxCharacters": 800}},
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            results = [{
                "title": r.get("title"),
                "url": r.get("url"),
                "text": (r.get("text") or "")[:800],
            } for r in data.get("results", [])]
            return {"ok": True, "provider": "exa", "query": query, "results": results}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": f"unknown search provider: {provider}"}
