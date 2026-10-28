import json
import pytest
from app.db.repository import OutreachRepository
from app.models import DiscoveryRequest, SearchResult
from app.services.discovery import DiscoveryService
from app.services.search_provider import MockSearchProvider, SearchProvider


@pytest.mark.asyncio
async def test_offline_discovery_uses_fictional_dataset_and_scores(tmp_path):
    repo=OutreachRepository(tmp_path/"db.sqlite3")
    response=await DiscoveryService(repo,MockSearchProvider(),None).discover(DiscoveryRequest(offline=True,buckets=["A","B","C"]))
    assert response["discovered_count"]>=10
    assert response["offline"] is True
    assert {p["detected_persona"] for p in response["profiles"]}=={"Fresher","1-2_YOE","Career_Switcher"}
    assert all(p["is_demo"] for p in response["profiles"])


class BrokenProvider(SearchProvider):
    async def search(self, query, max_results=10): raise RuntimeError("provider down")

@pytest.mark.asyncio
async def test_search_provider_errors_are_reported_not_fatal(tmp_path):
    response=await DiscoveryService(OutreachRepository(tmp_path/"db.sqlite3"),BrokenProvider()).discover(DiscoveryRequest(offline=True,buckets=["A"]))
    assert response["profiles"]==[]
    assert any("provider down" in error for error in response["errors"])
