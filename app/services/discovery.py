"""Discovery orchestration: public search -> strict URL normalization -> scoring -> dedupe."""
from __future__ import annotations

from app.db.repository import OutreachRepository
from app.models import DiscoveryRequest, OutreachPayload, SearchResult
from app.services.llm_service import LLMService
from app.services.query_builder import build_queries
from app.services.search_provider import SearchProvider, create_search_provider


class DiscoveryService:
    def __init__(self, repository: OutreachRepository | None = None, search_provider: SearchProvider | None = None, llm: LLMService | None = None) -> None:
        self.repository = repository or OutreachRepository()
        self.search_provider = search_provider
        self.llm = llm or LLMService()

    async def discover(self, request: DiscoveryRequest) -> dict:
        queries = build_queries(request)
        provider = self.search_provider or create_search_provider(offline=request.offline)
        discovered: dict[str, OutreachPayload] = {}
        errors: list[str] = []
        for query in queries.queries:
            try:
                profiles = await provider.search(query, request.max_results_per_bucket)
            except Exception as exc:
                errors.append(str(exc))
                continue
            for profile in profiles:
                try:
                    payload = self.llm.score(profile, offline=request.offline)
                except Exception as exc:
                    errors.append(f"Scoring failed for {profile.profile_url}: {exc}")
                    continue
                discovered[payload.profile_url] = payload
        results, duplicates = [], 0
        for payload in discovered.values():
            saved, inserted = self.repository.save_discovered(payload)
            if inserted:
                results.append(payload.model_dump())
            else:
                duplicates += 1
        return {"queries": queries.queries, "bucket_descriptions": queries.bucket_descriptions,
                "profiles": results, "discovered_count": len(results), "duplicate_count": duplicates,
                "errors": errors, "offline": request.offline, "demo_label": "Synthetic offline demonstration data" if request.offline else None}
