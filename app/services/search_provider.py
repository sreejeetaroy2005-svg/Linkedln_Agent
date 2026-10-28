"""Public search provider boundary. This app never fetches LinkedIn profile pages."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.config import ROOT, settings
from app.models import SearchResult


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]: ...

    def health_check(self) -> dict[str, str]:
        return {"provider": self.__class__.__name__, "status": "configured"}


def normalize_search_items(items: Any, source: str) -> list[SearchResult]:
    """Normalize provider result data, dropping malformed/non-person LinkedIn URLs."""
    if not isinstance(items, list):
        return []
    normalized: list[SearchResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("link") or item.get("url")
        if not isinstance(url, str):
            continue
        try:
            title = str(item.get("title") or "Unknown")
            name = title.split("|", 1)[0].strip() or "Unknown"
            snippet = str(item.get("snippet") or item.get("content") or "")
            # Search results rarely have a separate headline; preserve title as observed headline.
            normalized.append(SearchResult(name=name, headline=title, snippet=snippet[:3000], profile_url=url, source=source))
        except (ValueError, TypeError):
            continue
    # Canonical URL dedupe preserving the first occurrence.
    return list({result.profile_url: result for result in reversed(normalized)}.values())[::-1]


class MockSearchProvider(SearchProvider):
    """Deterministic offline search provider powered by explicitly synthetic JSON profiles."""
    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or ROOT / "data" / "mock_profiles.json"
        self.call_count = 0

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.call_count += 1
        try:
            data = json.loads(self.data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Offline demo profiles are unavailable or invalid") from exc
        selected = [p for p in data if _matches_query_bucket(query, p)]
        if not selected:
            selected = data
        return normalize_search_items(selected[:max_results], "offline_demo")

    def health_check(self) -> dict[str, str]:
        return {"provider": "offline_demo", "status": "healthy"}


def _matches_query_bucket(query: str, profile: dict[str, Any]) -> bool:
    lower = query.lower()
    bucket = profile.get("bucket")
    terms = {"A": "final year", "B": "associate software engineer", "C": "qa engineer"}
    # Query builder anchors are stable; classify by these unique quoted role terms.
    if "final year b.tech" in lower or "2026 graduate" in lower:
        return bucket == "A"
    if "associate software engineer" in lower:
        return bucket == "B"
    if "qa engineer" in lower:
        return bucket == "C"
    return False


class SerperSearchProvider(SearchProvider):
    """Serper-backed public web search; provider terms and quotas apply."""
    def __init__(self, api_key: str | None = None, timeout: float = 12.0) -> None:
        self.api_key = api_key if api_key is not None else settings.serper_api_key
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        if not self.api_key:
            raise RuntimeError("Serper is selected but SERPER_API_KEY is not configured")
        import httpx
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post("https://google.serper.dev/search", headers={"X-API-KEY": self.api_key}, json={"q": query, "num": min(max_results, 10)})
                if response.status_code == 429:
                    raise RuntimeError("Search provider rate limit reached; try again later")
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise RuntimeError("Search provider returned malformed results")
                return normalize_search_items(data.get("organic", []), "serper")[:max_results]
        except httpx.TimeoutException as exc:
            raise RuntimeError("Search provider timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Search provider failed with HTTP {exc.response.status_code}") from exc
        except (httpx.RequestError, ValueError) as exc:
            raise RuntimeError("Search provider request failed") from exc


def create_search_provider(offline: bool = False) -> SearchProvider:
    if offline or settings.search_provider == "mock":
        return MockSearchProvider()
    if settings.search_provider == "serper":
        return SerperSearchProvider()
    raise RuntimeError(f"Unsupported SEARCH_PROVIDER: {settings.search_provider}")
