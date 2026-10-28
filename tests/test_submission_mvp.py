import json
from pathlib import Path

from app.models import OutreachPayload, SearchResult, canonical_linkedin_url
from app.services.llm_service import LLMService

ROOT = Path(__file__).resolve().parents[1]


def test_mock_dataset_has_at_least_ten_fictional_profiles_across_buckets():
    profiles = json.loads((ROOT / "data" / "mock_profiles.json").read_text())
    assert len(profiles) >= 10
    assert {row["bucket"] for row in profiles} == {"A", "B", "C"}
    assert all("fictional" in row["snippet"].lower() for row in profiles)


def test_sample_output_has_exactly_three_valid_payloads_per_persona():
    samples = json.loads((ROOT / "sample_output.json").read_text())
    assert len(samples) == 9
    expected = {"Fresher": 3, "1-2_YOE": 3, "Career_Switcher": 3}
    assert {persona: sum(row["detected_persona"] == persona for row in samples) for persona in expected} == expected
    for sample in samples:
        OutreachPayload.model_validate(sample)
        assert len(sample["connection_note"]) < 300
        assert len(sample["follow_up_dm"].split()) < 100
        assert "https://code2careerai.com" in sample["follow_up_dm"]
        assert sample["is_demo"] is True


def test_offline_generator_is_deterministic_and_validated():
    profile = SearchResult(
        name="Demo Learner", headline="Final Year CS Student learning machine learning",
        snippet="Fictional demo profile studying Python.",
        profile_url="https://www.linkedin.com/in/demo-learner",
    )
    service = LLMService(api_key="")
    first = service.score(profile, offline=True)
    second = service.score(profile, offline=True)
    first_data, second_data = first.model_dump(), second.model_dump()
    first_data.pop("created_at")
    second_data.pop("created_at")
    assert first_data == second_data
    assert first.is_demo is True
    assert first.detected_persona == "Fresher"
    assert canonical_linkedin_url(first.profile_url) == first.profile_url
